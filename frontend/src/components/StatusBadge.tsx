import { cn } from "@/lib/utils";

const variants = {
  processing: "bg-blue-50 text-blue-700 border-blue-200",
  classified: "bg-green-50 text-green-700 border-green-200",
  needs_review: "bg-rose-50 text-rose-700 border-rose-200",
  error: "bg-rose-50 text-rose-700 border-rose-200",
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  received: "bg-green-50 text-green-700 border-green-200",
  connected: "bg-green-50 text-green-700 border-green-200",
  disconnected: "bg-zinc-50 text-zinc-500 border-zinc-200",
  draft: "bg-amber-50 text-amber-700 border-amber-200",
  sent: "bg-green-50 text-green-700 border-green-200",
  open: "bg-blue-50 text-blue-700 border-blue-200",
  answered: "bg-zinc-50 text-zinc-500 border-zinc-200",
} as const;

const labels: Record<string, string> = {
  processing: "Processing",
  classified: "Classified",
  needs_review: "Needs Review",
  error: "Error",
  pending: "Pending",
  received: "Received",
  connected: "Connected",
  disconnected: "Disconnected",
  draft: "Draft",
  sent: "Sent",
  open: "Open",
  answered: "Answered",
};

interface Props {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: Props) {
  const style = variants[status as keyof typeof variants] ?? "bg-zinc-50 text-zinc-500 border-zinc-200";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        style,
        className
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "processing" && "bg-blue-500 animate-pulse",
          status === "classified" && "bg-green-500",
          status === "received" && "bg-green-500",
          status === "connected" && "bg-green-500",
          status === "needs_review" && "bg-rose-500",
          status === "error" && "bg-rose-500",
          status === "pending" && "bg-amber-500",
          status === "draft" && "bg-amber-500",
          status === "sent" && "bg-green-500",
          status === "open" && "bg-blue-500",
          status === "disconnected" && "bg-zinc-400",
          status === "answered" && "bg-zinc-400",
        )}
      />
      {labels[status] ?? status}
    </span>
  );
}
