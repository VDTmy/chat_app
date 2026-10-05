interface TypingIndicatorProps {
  /** Array of user IDs currently typing */
  typingUserIds: string[];
}

export function TypingIndicator({ typingUserIds }: TypingIndicatorProps) {
  if (typingUserIds.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-3.5 py-2.5 bg-[#1e1e2a] rounded-2xl rounded-bl-sm w-fit">
      <span className="text-xs text-gray-500 font-medium">Đang nhập</span>
      <div className="flex items-center gap-1">
        <div
          className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
          style={{ animationDelay: "0ms", animationDuration: "1.2s" }}
        />
        <div
          className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
          style={{ animationDelay: "200ms", animationDuration: "1.2s" }}
        />
        <div
          className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"
          style={{ animationDelay: "400ms", animationDuration: "1.2s" }}
        />
      </div>
    </div>
  );
}
