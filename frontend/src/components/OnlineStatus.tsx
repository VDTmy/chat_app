import { cn } from "../lib/utils";

interface OnlineStatusProps {
  isOnline: boolean;
  size?: "sm" | "md";
  className?: string;
}

export function OnlineStatus({ isOnline, size = "md", className }: OnlineStatusProps) {
  const sizeClasses = size === "sm" ? "w-2.5 h-2.5 border-[1.5px]" : "w-3 h-3 border-2";

  return (
    <span
      className={cn(
        "absolute bottom-0 right-0 rounded-full border-[#13131c]",
        sizeClasses,
        isOnline ? "bg-green-500" : "bg-gray-600",
        className
      )}
    />
  );
}
