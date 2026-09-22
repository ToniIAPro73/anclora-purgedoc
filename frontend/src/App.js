import React, { useState, useEffect } from "react";
import axios from "axios";
import { AppProvider, useApp } from "./context/AppContext";
import { Header } from "./components/Header";
import { DevFixturesModal } from "./components/DevFixturesModal";
import { UploadScreen } from "./components/UploadScreen";
import { ProcessingStepper } from "./components/ProcessingStepper";
import { DocumentViewer } from "./components/DocumentViewer";
import { ReviewPanel } from "./components/ReviewPanel";
import { ConfirmationModal } from "./components/ConfirmationModal";
import { ResultsScreen } from "./components/ResultsScreen";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";

function PurgedocMainApp() {
  const { t } = useApp();

  // App Workflow Steps: 'upload' | 'analyzing' | 'review' | 'purging' | 'results'
  const [currentStep, setCurrentStep] = useState("upload");

  // State
  const [sessionId, setSessionId] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState("rrhh");
  const [documentMeta, setDocumentMeta] = useState(null);
  const [matches, setMatches] = useState([]);
  const [activeMatchId, setActiveMatchId] = useState(null);
  const [stepperStage, setStepperStage] = useState(1);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isDevFixturesOpen, setIsDevFixturesOpen] = useState(false);
  const [purgeResult, setPurgeResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Initialize ephemeral session
  useEffect(() => {
    async function initSession() {
      try {
        const res = await axios.post(`${BACKEND_URL}/api/sessions`);
        setSessionId(res.data.session_id);
      } catch (err) {
        console.error("Failed to initialize session:", err);
      }
    }
    initSession();
  }, []);

  // 1. Upload & Analyze Document
  const handleStartAnalysis = async () => {
    if (!selectedFile || !sessionId) return;
    setErrorMessage(null);
    setCurrentStep("analyzing");
    setStepperStage(1);

    try {
      // Step 1: Upload
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("profile_id", selectedProfile);

      setStepperStage(1);
      const uploadRes = await axios.post(
        `${BACKEND_URL}/api/sessions/${sessionId}/documents`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      const doc = uploadRes.data;
      setDocumentMeta(doc);

      // Step 2 & 3: Run Analysis (NER + Regex)
      setStepperStage(2);
      await new Promise((r) => setTimeout(r, 600)); // Smooth UX transition
      setStepperStage(3);

      const analyzeRes = await axios.post(`${BACKEND_URL}/api/documents/${doc.id}/analyze`);
      setDocumentMeta(analyzeRes.data.document);
      setMatches(analyzeRes.data.matches);

      setStepperStage(4);
      await new Promise((r) => setTimeout(r, 400));

      if (analyzeRes.data.matches.length > 0) {
        setActiveMatchId(analyzeRes.data.matches[0].id);
      }

      setCurrentStep("review");
    } catch (err) {
      console.error("Error analyzing document:", err);
      const detail = err.response?.data?.detail || "Error al procesar el archivo.";
      setErrorMessage(detail);
      setCurrentStep("upload");
    }
  };

  // 2. Load Synthetic Fixture (Dev/QA)
  const handleLoadFixture = async (fixtureKey, profileId) => {
    if (!sessionId) return;
    setErrorMessage(null);
    setCurrentStep("analyzing");
    setStepperStage(1);

    try {
      const res = await axios.post(
        `${BACKEND_URL}/api/fixtures/${fixtureKey}/load?session_id=${sessionId}&profile_id=${profileId}`
      );
      const doc = res.data;
      setDocumentMeta(doc);
      setSelectedProfile(profileId);

      setStepperStage(2);
      await new Promise((r) => setTimeout(r, 500));
      setStepperStage(3);

      const analyzeRes = await axios.post(`${BACKEND_URL}/api/documents/${doc.id}/analyze`);
      setDocumentMeta(analyzeRes.data.document);
      setMatches(analyzeRes.data.matches);

      setStepperStage(4);
      await new Promise((r) => setTimeout(r, 300));

      if (analyzeRes.data.matches.length > 0) {
        setActiveMatchId(analyzeRes.data.matches[0].id);
      }

      setCurrentStep("review");
    } catch (err) {
      console.error("Error loading fixture:", err);
      setErrorMessage(err.response?.data?.detail || "Error al cargar fixture sintético.");
      setCurrentStep("upload");
    }
  };

  // 3. Update Match Status (Single)
  const handleUpdateMatchStatus = async (matchId, newStatus) => {
    try {
      await axios.patch(`${BACKEND_URL}/api/matches/${matchId}`, { status: newStatus });
      setMatches((prev) =>
        prev.map((m) => (m.id === matchId ? { ...m, status: newStatus } : m))
      );
    } catch (err) {
      console.error("Failed to update match status:", err);
    }
  };

  // 4. Bulk Update Matches
  const handleBulkUpdate = async (newStatus) => {
    if (!documentMeta) return;
    try {
      await axios.post(`${BACKEND_URL}/api/documents/${documentMeta.id}/matches/bulk`, {
        all_visible: true,
        status: newStatus
      });
      setMatches((prev) => prev.map((m) => ({ ...m, status: newStatus })));
    } catch (err) {
      console.error("Failed to bulk update matches:", err);
    }
  };

  // 5. Execute Purge and Automated Fail-Closed Verification
  const handleExecutePurge = async () => {
    setIsConfirmModalOpen(false);
    setCurrentStep("purging");
    setStepperStage(1);

    try {
      setStepperStage(2);
      await new Promise((r) => setTimeout(r, 500));
      setStepperStage(3);

      const res = await axios.post(`${BACKEND_URL}/api/documents/${documentMeta.id}/purge`);
      setStepperStage(4);
      await new Promise((r) => setTimeout(r, 600));
      setStepperStage(5);

      setPurgeResult(res.data);
      setCurrentStep("results");
    } catch (err) {
      console.error("Purge failure:", err);
      setErrorMessage(err.response?.data?.detail || "Error crítico durante la purga y verificación.");
      setCurrentStep("review");
    }
  };

  // Restart workflow
  const handleRestart = () => {
    setSelectedFile(null);
    setDocumentMeta(null);
    setMatches([]);
    setActiveMatchId(null);
    setPurgeResult(null);
    setErrorMessage(null);
    setCurrentStep("upload");
  };

  const acceptedCount = matches.filter((m) => m.status === "accepted").length;
  const pendingCount = matches.filter((m) => m.status === "pending").length;

  return (
    <div className="min-h-screen flex flex-col bg-[#0B0F19] text-slate-100 transition-colors dark:bg-[#0B0F19] dark:text-slate-100 light:bg-[#F8FAFC] light:text-slate-900">
      
      {/* Global Header */}
      <Header onOpenDevFixtures={() => setIsDevFixturesOpen(true)} />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col">
        {currentStep === "upload" && (
          <UploadScreen
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            selectedProfile={selectedProfile}
            setSelectedProfile={setSelectedProfile}
            onStartAnalysis={handleStartAnalysis}
            errorMessage={errorMessage}
          />
        )}

        {currentStep === "analyzing" && (
          <ProcessingStepper activeStage={stepperStage} isPurging={false} />
        )}

        {currentStep === "review" && (
          <div className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-5rem)]">
            {/* Left Column: Synchronized Document Viewer (7 cols) */}
            <div className="lg:col-span-7 h-full">
              <DocumentViewer
                documentId={documentMeta?.id}
                pageCount={documentMeta?.page_count || 1}
                matches={matches}
                activeMatchId={activeMatchId}
                onSelectMatch={(id) => setActiveMatchId(id)}
                backendUrl={BACKEND_URL}
              />
            </div>

            {/* Right Column: Review Panel (5 cols) */}
            <div className="lg:col-span-5 h-full">
              <ReviewPanel
                matches={matches}
                activeMatchId={activeMatchId}
                onSelectMatch={(id) => setActiveMatchId(id)}
                onUpdateStatus={handleUpdateMatchStatus}
                onBulkUpdate={handleBulkUpdate}
                onTriggerPurgeModal={() => setIsConfirmModalOpen(true)}
              />
            </div>
          </div>
        )}

        {currentStep === "purging" && (
          <ProcessingStepper activeStage={stepperStage} isPurging={true} />
        )}

        {currentStep === "results" && (
          <ResultsScreen
            purgeResult={purgeResult}
            documentMeta={documentMeta}
            backendUrl={BACKEND_URL}
            onRestart={handleRestart}
          />
        )}
      </main>

      {/* Confirmation Modal */}
      <ConfirmationModal
        isOpen={isConfirmModalOpen}
        onClose={() => setIsConfirmModalOpen(false)}
        onConfirmPurge={handleExecutePurge}
        acceptedCount={acceptedCount}
        pendingCount={pendingCount}
      />

      {/* Dev/QA Fixtures Modal */}
      <DevFixturesModal
        isOpen={isDevFixturesOpen}
        onClose={() => setIsDevFixturesOpen(false)}
        onLoadFixture={handleLoadFixture}
      />

    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <PurgedocMainApp />
    </AppProvider>
  );
}
