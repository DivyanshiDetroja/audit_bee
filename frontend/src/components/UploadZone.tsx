import { useRef, useState, DragEvent, ChangeEvent } from "react";
import { Upload, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "./Spinner";

interface Props {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
  label?: string;
}

export function UploadZone({
  onUpload,
  accept = ".pdf,.png,.jpg,.jpeg,.tiff,.webp",
  label = "Upload document",
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handle(file: File) {
    setError(null);
    setUploading(true);
    try {
      await onUpload(file);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handle(file);
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handle(file);
    e.target.value = "";
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        disabled={uploading}
        className={cn(
          "w-full rounded-lg border-2 border-dashed px-6 py-8 transition-colors text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B6CF6]",
          dragging
            ? "border-[#3B6CF6] bg-blue-50"
            : "border-[#E6E8EC] bg-[#F7F8FA] hover:border-[#3B6CF6] hover:bg-blue-50/40",
          uploading && "opacity-60 cursor-not-allowed"
        )}
      >
        <div className="flex flex-col items-center gap-2">
          {uploading ? (
            <Spinner className="h-6 w-6 text-[#3B6CF6]" />
          ) : (
            <Upload className="h-6 w-6 text-[#5B6270]" />
          )}
          <div>
            <p className="text-sm font-medium text-[#16181D]">
              {uploading ? "Uploading…" : label}
            </p>
            <p className="text-xs text-[#5B6270] mt-0.5">
              {uploading
                ? "Document is being sent for processing"
                : "Drag and drop or click to select — PDF, PNG, JPG, TIFF"}
            </p>
          </div>
        </div>
      </button>
      {error && (
        <p className="mt-2 text-xs text-rose-600 flex items-center gap-1">
          <FileText className="h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={onChange}
      />
    </div>
  );
}
