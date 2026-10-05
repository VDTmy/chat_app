import { useState } from "react";
import { format } from "date-fns";
import { Check, CheckCheck, CornerUpLeft, FileText, Download, X } from "lucide-react";
import type { Message } from "../types";
import { cn } from "../lib/utils";

interface MessageBubbleProps {
  message: Message;
  isOwn: boolean;
  /** Show avatar + sender name for the last msg in a consecutive block */
  showAvatar?: boolean;
  replyToMessage?: Message;
  /** Sender's username (for group chats) */
  senderName?: string;
  /** True if this is inside a group conversation */
  isGroup?: boolean;
  /** Called when the user clicks the reply button */
  onReply?: (message: Message) => void;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function getFileExtension(url: string): string {
  try {
    const pathname = new URL(url).pathname;
    return pathname.split(".").pop()?.toLowerCase() ?? "";
  } catch {
    return url.split(".").pop()?.toLowerCase() ?? "";
  }
}

function isImageUrl(url: string): boolean {
  return ["jpg", "jpeg", "png", "gif", "webp"].includes(getFileExtension(url));
}

function isVideoUrl(url: string): boolean {
  return ["mp4", "webm", "ogg"].includes(getFileExtension(url));
}

function isPdfUrl(url: string): boolean {
  return getFileExtension(url) === "pdf";
}

// ── FileContent — renders the appropriate media widget ───────────────────────

function FileContent({ url, isOwn }: { url: string; isOwn: boolean }) {
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const isImage = isImageUrl(url);
  const isVideo = isVideoUrl(url);
  const isPdf = isPdfUrl(url);

  // ── Image ──
  if (isImage) {
    return (
      <>
        <button
          onClick={() => setLightboxOpen(true)}
          className="block overflow-hidden rounded-xl max-w-[280px] focus:outline-none focus:ring-2 focus:ring-blue-400"
          title="Xem ảnh"
        >
          <img
            src={url}
            alt="Ảnh đính kèm"
            className="max-w-[280px] max-h-[320px] object-cover rounded-xl transition-opacity hover:opacity-90"
            loading="lazy"
          />
        </button>

        {/* Lightbox */}
        {lightboxOpen && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
            onClick={() => setLightboxOpen(false)}
          >
            <button
              className="absolute top-4 right-4 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full p-2 transition-all"
              onClick={() => setLightboxOpen(false)}
            >
              <X size={20} />
            </button>
            <img
              src={url}
              alt="Xem ảnh đầy đủ"
              className="max-w-[90vw] max-h-[90vh] object-contain rounded-xl shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </>
    );
  }

  // ── Video ──
  if (isVideo) {
    return (
      <video
        controls
        className="max-w-[280px] max-h-[240px] rounded-xl"
        preload="metadata"
      >
        <source src={url} type="video/mp4" />
        Trình duyệt không hỗ trợ video.
      </video>
    );
  }

  // ── PDF ──
  if (isPdf) {
    const fileName = decodeURIComponent(url.split("/").pop()?.split("?")[0] ?? "document.pdf");
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        download
        className={cn(
          "flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-colors max-w-[240px]",
          isOwn
            ? "bg-blue-700/30 border-blue-400/30 hover:bg-blue-700/40 text-blue-100"
            : "bg-white/5 border-white/10 hover:bg-white/10 text-gray-200"
        )}
      >
        <FileText size={20} className="flex-shrink-0 text-red-400" />
        <span className="text-sm truncate flex-1">{fileName}</span>
        <Download size={14} className="flex-shrink-0 opacity-60" />
      </a>
    );
  }

  // ── Generic file download ──
  const fileName = decodeURIComponent(url.split("/").pop()?.split("?")[0] ?? "file");
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      download
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-colors max-w-[240px]",
        isOwn
          ? "bg-blue-700/30 border-blue-400/30 hover:bg-blue-700/40 text-blue-100"
          : "bg-white/5 border-white/10 hover:bg-white/10 text-gray-200"
      )}
    >
      <Download size={18} className="flex-shrink-0 opacity-70" />
      <span className="text-sm truncate flex-1">{fileName}</span>
    </a>
  );
}

// ── MessageBubble ─────────────────────────────────────────────────────────────

export function MessageBubble({
  message,
  isOwn,
  showAvatar = false,
  replyToMessage,
  senderName,
  isGroup = false,
  onReply,
}: MessageBubbleProps) {
  const isDeleted = message.is_deleted;
  const isFileMessage =
    !isDeleted && (message.message_type === "image" || message.message_type === "file");

  return (
    <div
      className={cn(
        "flex w-full mb-1",
        isOwn ? "justify-end" : "justify-start",
        showAvatar ? "mb-3" : "mb-0.5"
      )}
    >
      {/* Avatar placeholder (left side for others) */}
      {!isOwn && (
        <div className="w-8 flex-shrink-0 mr-2 self-end">
          {showAvatar ? (
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-semibold select-none">
              {(senderName ?? "U").charAt(0).toUpperCase()}
            </div>
          ) : null}
        </div>
      )}

      {/* Bubble column */}
      <div className={cn("flex flex-col max-w-[70%]", isOwn ? "items-end" : "items-start")}>
        {/* Sender name in group for first msg of block */}
        {!isOwn && isGroup && showAvatar && senderName && (
          <span className="text-xs text-gray-500 mb-0.5 ml-1">{senderName}</span>
        )}

        {/* Reply quote */}
        {replyToMessage && !isDeleted && (
          <div
            className={cn(
              "px-3 py-1.5 mb-1 rounded-xl text-xs border-l-4 max-w-full",
              isOwn
                ? "bg-blue-700/30 border-blue-400/60 text-blue-200"
                : "bg-white/5 border-gray-500/40 text-gray-400"
            )}
          >
            <p className="font-semibold mb-0.5 opacity-70">
              {replyToMessage.sender_id === message.sender_id
                ? "Đã trả lời chính mình"
                : "Đã trả lời"}
            </p>
            <p className="truncate line-clamp-1 opacity-80">{replyToMessage.content}</p>
          </div>
        )}

        {/* Main bubble — group element holds hover state for the reply button */}
        <div className="relative group flex items-center gap-1.5">
          {/* Reply button — appears on hover (left of own, right of other) */}
          {!isDeleted && onReply && isOwn && (
            <button
              onClick={() => onReply(message)}
              title="Trả lời"
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-full text-gray-500 hover:text-blue-400 hover:bg-white/10 flex-shrink-0 order-first"
            >
              <CornerUpLeft size={14} />
            </button>
          )}

          {/* Timestamp tooltip — left of own bubble */}
          {isOwn && (
            <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[11px] text-gray-600 whitespace-nowrap select-none">
              {format(new Date(message.created_at), "HH:mm")}
            </span>
          )}

          {/* ── Bubble or File widget ── */}
          {isFileMessage ? (
            /* File messages: render media directly (no text bubble wrapper) */
            <FileContent url={message.content} isOwn={isOwn} />
          ) : (
            <div
              className={cn(
                "px-3.5 py-2 rounded-2xl text-sm leading-relaxed break-words whitespace-pre-wrap max-w-full",
                isOwn
                  ? "bg-blue-600 text-white rounded-br-sm"
                  : "bg-[#1e1e2a] text-gray-100 rounded-bl-sm",
                isDeleted &&
                  "italic bg-transparent border border-white/10 text-gray-600 px-3 py-1.5"
              )}
            >
              {isDeleted ? "Tin nhắn đã bị xóa" : message.content}
            </div>
          )}

          {/* Timestamp tooltip — right of other's bubble */}
          {!isOwn && (
            <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[11px] text-gray-600 whitespace-nowrap select-none">
              {format(new Date(message.created_at), "HH:mm")}
            </span>
          )}

          {/* Reply button for other's messages (appears on right) */}
          {!isDeleted && onReply && !isOwn && (
            <button
              onClick={() => onReply(message)}
              title="Trả lời"
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-full text-gray-500 hover:text-blue-400 hover:bg-white/10 flex-shrink-0"
            >
              <CornerUpLeft size={14} />
            </button>
          )}
        </div>

        {/* Read receipts for own messages */}
        {isOwn && !isDeleted && (
          <div className="flex items-center justify-end mt-0.5 gap-1">
            {message.is_read ? (
              <>
                <CheckCheck size={13} className="text-blue-400" />
                <span className="text-[10px] text-blue-400">Đã xem</span>
              </>
            ) : (
              <>
                <Check size={13} className="text-gray-600" />
                <span className="text-[10px] text-gray-600">Đã gửi</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
