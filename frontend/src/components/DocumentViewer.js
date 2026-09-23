import React, { useState, useEffect, useRef } from "react";
import { useApp } from "../context/AppContext";
import {
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  FileCheck
} from "lucide-react";

export const DocumentViewer = ({
  documentId,
  pageCount = 1,
  matches = [],
  activeMatchId,
  onSelectMatch,
  backendUrl
}) => {
  const { t } = useApp();
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1.0);
  const containerRef = useRef(null);

  // When activeMatchId changes, auto-navigate to its page
  useEffect(() => {
    if (activeMatchId) {
      const activeMatch = matches.find((m) => m.id === activeMatchId);
      if (activeMatch && activeMatch.page !== currentPage) {
        setCurrentPage(activeMatch.page);
      }
    }
  }, [activeMatchId, matches, currentPage]);

  const handlePrevPage = () => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage((prev) => Math.min(pageCount, prev + 1));
  };

  const pageMatches = matches.filter((m) => m.page === currentPage);
  const imageUrl = `${backendUrl}/api/documents/${documentId}/page-image/${currentPage}`;

  return (
    <div className="flex flex-col h-full bg-[#0B0F19] rounded-2xl border border-slate-800 overflow-hidden shadow-xl">
      
      {/* Top Toolbar */}
      <div className="h-12 border-b border-slate-800 bg-[#111827] px-4 flex items-center justify-between text-xs text-slate-300">
        
        {/* Page navigation */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="doc-prev-page-btn"
            disabled={currentPage <= 1}
            onClick={handlePrevPage}
            className="p-1 rounded hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="font-mono text-slate-200">
            {t("page")} <strong className="text-cyan-400">{currentPage}</strong> {t("of")} {pageCount}
          </span>
          <button
            type="button"
            data-testid="doc-next-page-btn"
            disabled={currentPage >= pageCount}
            onClick={handleNextPage}
            className="p-1 rounded hover:bg-slate-800 disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="doc-zoom-out-btn"
            onClick={() => setZoom((z) => Math.max(0.6, z - 0.15))}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
            title="Reducir zoom"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="font-mono text-[11px] w-12 text-center text-cyan-300">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            data-testid="doc-zoom-in-btn"
            onClick={() => setZoom((z) => Math.min(1.8, z + 0.15))}
            className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
            title="Aumentar zoom"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>

      {/* Viewer Canvas Area */}
      <div
        ref={containerRef}
        data-testid="doc-viewer-canvas"
        className="flex-1 overflow-auto p-4 flex justify-center items-start bg-slate-950/60"
      >
        <div
          className="relative shadow-2xl transition-transform duration-100 origin-top"
          style={{ transform: `scale(${zoom})` }}
        >
          {/* Rendered high-res Page image */}
          <img
            src={imageUrl}
            alt={`Page ${currentPage}`}
            className="max-w-none rounded border border-slate-700 bg-white"
            style={{ width: "595px", height: "842px", objectFit: "contain" }}
          />

          {/* Synchronized Bounding Box Overlays */}
          {pageMatches.map((m) => {
            if (!m.bbox) return null;
            const { x0, y0, x1, y1, page_width, page_height } = m.bbox;
            const left = (x0 / page_width) * 100;
            const top = (y0 / page_height) * 100;
            const width = ((x1 - x0) / page_width) * 100;
            const height = ((y1 - y0) / page_height) * 100;

            const isSelected = activeMatchId === m.id;
            const isAccepted = m.status === "accepted";
            const isRejected = m.status === "rejected";

            let borderClass = "border-amber-400/80 bg-amber-400/20";
            if (isAccepted) {
              borderClass = "border-rose-500 bg-rose-500/30";
            } else if (isRejected) {
              borderClass = "border-slate-500/60 bg-slate-500/10";
            }

            if (isSelected) {
              borderClass += " ring-2 ring-cyan-400 shadow-[0_0_12px_rgba(56,189,248,0.6)]";
            }

            return (
              <div
                key={m.id}
                data-testid={`canvas-bbox-${m.id}`}
                onClick={() => onSelectMatch(m.id)}
                className={`absolute cursor-pointer border rounded-sm transition-all duration-150 ${borderClass}`}
                style={{
                  left: `${left}%`,
                  top: `${top}%`,
                  width: `${Math.max(width, 2)}%`,
                  height: `${Math.max(height, 2)}%`
                }}
                title={`${m.entity_type} (${m.status})`}
              />
            );
          })}
        </div>
      </div>

    </div>
  );
};
