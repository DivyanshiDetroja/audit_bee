/**
 * The signature document-processing reveal card (DESIGN.md §9.1).
 * Animates Received → Reading → Classified and surfaces extracted fields.
 * Polls /documents/:id every 2 s while status=processing.
 * Amounts and IDs rendered in IBM Plex Mono.
 */
import { useEffect, useRef, useState } from "react";
import { FileText, CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { api, Document } from "@/api";
import { StatusBadge } from "./StatusBadge";

interface Props {
  doc: Document;
  onUpdated?: (doc: Document) => void;
}

type Stage = "received" | "reading" | "classified" | "needs_review" | "error";

function toStage(status: Document["status"]): Stage {
  if (status === "classified") return "classified";
  if (status === "needs_review") return "needs_review";
  if (status === "error") return "error";
  if (status === "processing") return "reading";
  return "received";
}

function KeyAmount({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null;
  return (
    <div className="flex justify-between items-baseline gap-4 py-1 border-b border-[#E6E8EC] last:border-0">
      <span className="text-xs text-[#5B6270]">{label}</span>
      <span className="font-mono text-xs font-medium text-[#16181D]">
        {String(value)}
      </span>
    </div>
  );
}

export function DocumentCard({ doc: initial, onUpdated }: Props) {
  const [doc, setDoc] = useState(initial);
  const stage = toStage(doc.status);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setDoc(initial);
  }, [initial.id]);

  // Poll while processing
  useEffect(() => {
    if (doc.status !== "processing") {
      if (pollingRef.current) clearInterval(pollingRef.current);
      return;
    }
    pollingRef.current = setInterval(async () => {
      try {
        const docs = await api.clientDocuments(doc.client_id);
        const updated = docs.find((d) => d.id === doc.id);
        if (updated && updated.status !== "processing") {
          setDoc(updated);
          onUpdated?.(updated);
          if (pollingRef.current) clearInterval(pollingRef.current);
        }
      } catch {
        // silently ignore poll errors
      }
    }, 2000);

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [doc.id, doc.status]);

  const fields = doc.extracted_fields as Record<string, unknown> | null;
  const keyAmounts = fields?.key_amounts as Record<string, unknown> | null;

  return (
    <div
      className={cn(
        "rounded-lg border bg-white shadow-card transition-all duration-500",
        stage === "reading" && "border-blue-200 shadow-blue-50",
        stage === "classified" && "border-green-200",
        stage === "needs_review" && "border-rose-200",
        stage === "error" && "border-rose-200",
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-4 border-b border-[#E6E8EC]">
        <div
          className={cn(
            "mt-0.5 rounded-md p-1.5 transition-colors duration-500",
            stage === "received" && "bg-zinc-100 text-zinc-500",
            stage === "reading" && "bg-blue-100 text-blue-600",
            stage === "classified" && "bg-green-100 text-green-600",
            stage === "needs_review" && "bg-rose-100 text-rose-600",
            stage === "error" && "bg-rose-100 text-rose-600",
          )}
        >
          {stage === "reading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : stage === "classified" ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : stage === "needs_review" || stage === "error" ? (
            <AlertCircle className="h-4 w-4" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[#16181D] truncate">
            {doc.normalized_filename ?? doc.original_filename}
          </p>
          <p className="text-xs text-[#5B6270] truncate mt-0.5">
            {doc.original_filename}
          </p>
        </div>

        <StatusBadge status={doc.status === "processing" ? "processing" : stage} />
      </div>

      {/* Processing animation */}
      {stage === "reading" && (
        <div className="px-4 py-3 bg-blue-50 border-b border-blue-100">
          <div className="flex items-center gap-2 text-blue-700">
            <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
            <span className="text-xs font-medium">
              Reading document — identifying type and extracting fields…
            </span>
          </div>
          <div className="mt-2 h-1 rounded-full bg-blue-100 overflow-hidden">
            <div className="h-full bg-blue-400 rounded-full animate-[shimmer_1.5s_ease-in-out_infinite] w-1/2" />
          </div>
        </div>
      )}

      {/* Classified: extracted fields */}
      {stage === "classified" && (
        <div className="p-4 space-y-3">
          <div className="flex flex-wrap gap-3">
            {doc.doc_type && (
              <div className="rounded-md bg-[#F7F8FA] border border-[#E6E8EC] px-3 py-1.5">
                <p className="text-[10px] text-[#5B6270] uppercase tracking-wide mb-0.5">Type</p>
                <p className="font-mono text-xs font-semibold text-[#16181D]">{doc.doc_type}</p>
              </div>
            )}
            {doc.tax_year && (
              <div className="rounded-md bg-[#F7F8FA] border border-[#E6E8EC] px-3 py-1.5">
                <p className="text-[10px] text-[#5B6270] uppercase tracking-wide mb-0.5">Tax Year</p>
                <p className="font-mono text-xs font-semibold text-[#16181D]">{doc.tax_year}</p>
              </div>
            )}
            {fields?.issuer != null && (
              <div className="rounded-md bg-[#F7F8FA] border border-[#E6E8EC] px-3 py-1.5">
                <p className="text-[10px] text-[#5B6270] uppercase tracking-wide mb-0.5">Issuer</p>
                <p className="text-xs font-semibold text-[#16181D]">{String(fields.issuer)}</p>
              </div>
            )}
          </div>

          {keyAmounts && Object.keys(keyAmounts).length > 0 && (
            <div className="rounded-md border border-[#E6E8EC] overflow-hidden">
              <div className="px-3 py-1.5 bg-[#F7F8FA] border-b border-[#E6E8EC]">
                <p className="text-[10px] uppercase tracking-wide text-[#5B6270] font-medium">
                  Key Amounts
                </p>
              </div>
              <div className="px-3 py-1">
                {Object.entries(keyAmounts).map(([k, v]) => (
                  <KeyAmount key={k} label={k.replace(/_/g, " ")} value={v} />
                ))}
              </div>
            </div>
          )}

          {doc.extracted_summary && (
            <p className="text-xs text-[#5B6270] leading-relaxed">{doc.extracted_summary}</p>
          )}
        </div>
      )}

      {/* Needs review */}
      {stage === "needs_review" && (
        <div className="px-4 py-3 bg-rose-50">
          <p className="text-xs text-rose-700">
            This document couldn't be confidently classified. Review and classify it manually.
          </p>
        </div>
      )}

      {/* Footer meta */}
      <div className="px-4 py-2.5 border-t border-[#E6E8EC] flex items-center justify-between">
        <span className="font-mono text-[10px] text-[#5B6270]">
          {new Date(doc.uploaded_at).toLocaleDateString("en-US", {
            month: "short", day: "numeric", year: "numeric",
          })}
          {" · "}
          {doc.source_channel === "email_sim"
            ? "via email"
            : doc.source_channel === "scan_sim"
            ? "via scan"
            : "via portal"}
        </span>
      </div>
    </div>
  );
}
