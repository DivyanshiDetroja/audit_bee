import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  icon?: ReactNode;
  heading: string;
  body: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, heading, body, action, className }: Props) {
  return (
    <div className={cn("flex flex-col items-center justify-center py-16 px-6 text-center", className)}>
      {icon && (
        <div className="mb-4 text-[#5B6270]">{icon}</div>
      )}
      <p className="text-sm font-medium text-[#16181D] mb-1">{heading}</p>
      <p className="text-sm text-[#5B6270] max-w-xs">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
