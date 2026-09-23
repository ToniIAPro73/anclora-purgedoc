import React, { useState, useEffect } from "react";
import axios from "axios";
import { AppProvider, useApp } from "./context/AppContext";
import { Header } from "./components/Header";
import { DevFixturesModal } from "./components/DevFixturesModal";
import { UploadScreen } from "./components/UploadScreen";
import { BatchQueueScreen } from "./components/BatchQueueScreen";
import { ProcessingStepper } from "./components/ProcessingStepper";
import { DocumentViewer } from "./components/DocumentViewer";
import { ReviewPanel } from "./components/ReviewPanel";
import { ConfirmationModal } from "./components/ConfirmationModal";
import { ResultsScreen } from "./components/ResultsScreen";
import { CustomRulesetEditor } from "./components/CustomRulesetEditor";
import { ArrowLeft, ArrowRight } from "lucide-react";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function PurgedocMainApp() {
  const { t } = useApp();

  // Mode: 'single' | 'batch'
  const [activeMode, setActiveMode] = useState("single");

  // Single Workflow Steps: 'upload' | 'analyzing' | 'review' | 'purging' | 'results'
  const [currentStep, setCurrentStep] = useState("upload");

  // Session & Single Document State
  const [sessionId, setSessionId] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState("rrhh");
  const [documentMeta, setDocumentMeta] = useState(null);
  const [matches, setMatches] = useState([]);
  const [activeMatchId, setActiveMatchId] = useState(null);
  const [stepperStage, setStepperStage] = useState(1);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isDevFixturesOpen, setIsDevFixturesOpen] = useState(false);
  const [isRulesEditorOpen, setIsRulesEditorOpen] = useState(false);
  const [purgeResult, setPurgeResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Batch State
  const [batchId, setBatchId] = useState(null);
  const [batchDetails, setBatchDetails] = useState(null);
  const [batchReviewingDocId, setBatchReviewingDocId] = useState(null);

  // Custom Ruleset State (Persisted in localStorage)
  const [customRules, setCustomRules] = useState(() => {
    try {
      const saved = localStorage.getItem("anclora_custom_rules");
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  });

  const activeCustomRulesCount = customRules.filter((r) => r.enabled).length;

  // Initialize ephemeral session and initial batch
  useEffect(() => {
    async function initSession() {
      try {
        const res = await axios.post(`${BACKEND_URL}/api/sessions`);
        const sId = res.data.session_id;
        setSessionId(sId);

        // Also create an initial draft batch for seamless batch mode
        const bRes = await axios.post(`${BACKEND_URL}/api/sessions/${sId}/batches`, {
          default_profile_id: "rrhh",
          custom_rules: customRules,
          ruleset_id: "batch_custom_ruleset",
          ruleset_version: "1.0.0"
        });
        setBatchId(bRes.data.id);
        const bDetailsRes = await axios.get(`${BACKEND_URL}/api/batches/${bRes.data.id}`);
        setBatchDetails(bDetailsRes.data);
      } catch (err) {
        console.error("Failed to initialize session/batch:", err);
      }
    }
    initSession();
  }, []);

  // Fetch / refresh batch details
  const refreshBatch = async (targetBatchId = batchId) => {
    if (!targetBatchId) return;
    try {
      const res = await axios.get(`${BACKEND_URL}/api/batches/${targetBatchId}`);
      setBatchDetails(res.data);
    } catch (err) {
      console.error("Error refreshing batch:", err);
    }
  };

  // Toggle Single vs Batch Mode
  const handleToggleMode = () => {
    if (activeMode === "single") {
      setActiveMode("batch");
      setBatchReviewingDocId(null);
      refreshBatch();
    } else {
      setActiveMode("single");
      setBatchReviewingDocId(null);
    }
  };

  // 1. Upload & Analyze Document (Single Mode)
  const handleStartAnalysis = async () => {
    if (!selectedFile || !sessionId) return;
    setErrorMessage(null);
    setCurrentStep("analyzing");
    setStepperStage(1);

    try {
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

      setStepperStage(2);
      await new Promise((r) => setTimeout(r, 600));
      setStepperStage(3);

      const analyzeRes = await axios.post(`${BACKEND_URL}/api/documents/${doc.id}/analyze`, {
        custom_rules: customRules,
        ruleset_id: "user_custom_ruleset",
        ruleset_version: "1.0.0"
      });
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

      const analyzeRes = await axios.post(`${BACKEND_URL}/api/documents/${doc.id}/analyze`, {
        custom_rules: customRules,
        ruleset_id: "user_custom_ruleset",
        ruleset_version: "1.0.0"
      });
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

  // 3. Update Match Status (Single or Batch Document)
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

      if (activeMode === "batch") {
        await refreshBatch();
        // Return to batch review list or stay in results
        setCurrentStep("results");
      } else {
        setCurrentStep("results");
      }
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
    if (activeMode === "batch") {
      setBatchReviewingDocId(null);
      refreshBatch();
    } else {
      setCurrentStep("upload");
    }
  };

  // Open Document from Batch for Review
  const handleSelectBatchDocumentForReview = async (docId) => {
    try {
      const docRes = await axios.get(`${BACKEND_URL}/api/batches/${batchId}`);
      const foundDoc = docRes.data.documents.find((d) => d.id === docId);
      if (!foundDoc) return;

      const matchesRes = await axios.get(`${BACKEND_URL}/api/documents/${docId}/matches`);
      setDocumentMeta(foundDoc);
      setMatches(matchesRes.data);
      if (matchesRes.data.length > 0) {
        setActiveMatchId(matchesRes.data[0].id);
      } else {
        setActiveMatchId(null);
      }
      setBatchReviewingDocId(docId);
      setCurrentStep("review");
    } catch (err) {
      console.error("Error opening batch document for review:", err);
    }
  };

  // Navigation between documents in batch review
  const handleNavigateBatchDoc = (direction) => {
    if (!batchDetails?.documents || !batchReviewingDocId) return;
    const reviewableDocs = batchDetails.documents.filter(
      (d) => d.status === "awaiting_review" || d.status === "ready_to_purge" || d.status === "verified"
    );
    const currentIndex = reviewableDocs.findIndex((d) => d.id === batchReviewingDocId);
    if (currentIndex === -1) return;

    const nextIndex = direction === "next" ? currentIndex + 1 : currentIndex - 1;
    if (nextIndex >= 0 && nextIndex < reviewableDocs.length) {
      handleSelectBatchDocumentForReview(reviewableDocs[nextIndex].id);
    }
  };

  const currentBatchDocs = batchDetails?.documents || [];
  const currentBatchIndex = currentBatchDocs.findIndex((d) => d.id === batchReviewingDocId);
  const hasPrevDoc = currentBatchIndex > 0;
  const hasNextDoc = currentBatchIndex >= 0 && currentBatchIndex < currentBatchDocs.length - 1;

  const acceptedCount = matches.filter((m) => m.status === "accepted").length;
  const pendingCount = matches.filter((m) => m.status === "pending").length;

  return (
    <div className="min-h-screen flex flex-col bg-[#0B0F19] text-slate-100 transition-colors dark:bg-[#0B0F19] dark:text-slate-100 light:bg-[#F8FAFC] light:text-slate-900">
      
      {/* Global Header with Mode Switcher & Rules Editor */}
      <Header
        onOpenDevFixtures={() => setIsDevFixturesOpen(true)}
        onOpenRulesEditor={() => setIsRulesEditorOpen(true)}
        customRulesCount={activeCustomRulesCount}
        activeMode={activeMode}
        onToggleMode={handleToggleMode}
        sessionId={sessionId}
        BACKEND_URL={BACKEND_URL}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col">
        {/* BATCH MODE VIEW */}
        {activeMode === "batch" && !batchReviewingDocId && (
          <BatchQueueScreen
            backendUrl={BACKEND_URL}
            sessionId={sessionId}
            batchId={batchId}
            batchDetails={batchDetails}
            onRefreshBatch={refreshBatch}
            onSelectDocumentForReview={handleSelectBatchDocumentForReview}
            customRules={customRules}
            onOpenRulesEditor={() => setIsRulesEditorOpen(true)}
          />
        )}

        {/* SINGLE MODE OR BATCH REVIEW STEP: UPLOAD */}
        {activeMode === "single" && currentStep === "upload" && (
          <UploadScreen
            selectedFile={selectedFile}
            setSelectedFile={setSelectedFile}
            selectedProfile={selectedProfile}
            setSelectedProfile={setSelectedProfile}
            onStartAnalysis={handleStartAnalysis}
            errorMessage={errorMessage}
            customRulesCount={activeCustomRulesCount}
            onOpenRulesEditor={() => setIsRulesEditorOpen(true)}
          />
        )}

        {currentStep === "analyzing" && (
          <ProcessingStepper activeStage={stepperStage} isPurging={false} />
        )}

        {/* REVIEW STEP (Used by both Single Mode and Batch Review) */}
        {currentStep === "review" && (
          <div className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 flex flex-col h-[calc(100vh-5rem)]">
            
            {/* Batch Navigation Sub-header if reviewing from batch */}
            {activeMode === "batch" && (
              <div className="pb-3 mb-3 border-b border-slate-800 flex items-center justify-between">
                <button
                  type="button"
                  data-testid="back-to-batch-queue-btn"
                  onClick={() => {
                    setBatchReviewingDocId(null);
                    setCurrentStep("upload");
                    refreshBatch();
                  }}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{t("batch_btn_back_to_queue")}</span>
                </button>

                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-slate-400">
                    Doc {currentBatchIndex + 1} de {currentBatchDocs.length}: <strong className="text-white">{documentMeta?.filename}</strong>
                  </span>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      data-testid="batch-prev-doc-btn"
                      disabled={!hasPrevDoc}
                      onClick={() => handleNavigateBatchDoc("prev")}
                      className="px-2.5 py-1 text-xs rounded bg-slate-900 border border-slate-700 text-slate-300 disabled:opacity-40"
                    >
                      {t("batch_prev_doc")}
                    </button>
                    <button
                      type="button"
                      data-testid="batch-next-doc-btn"
                      disabled={!hasNextDoc}
                      onClick={() => handleNavigateBatchDoc("next")}
                      className="px-2.5 py-1 text-xs rounded bg-slate-900 border border-slate-700 text-slate-300 disabled:opacity-40"
                    >
                      {t("batch_next_doc")}
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
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

      {/* Custom Ruleset Editor Modal */}
      <CustomRulesetEditor
        isOpen={isRulesEditorOpen}
        onClose={() => setIsRulesEditorOpen(false)}
        backendUrl={BACKEND_URL}
        customRules={customRules}
        setCustomRules={setCustomRules}
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
