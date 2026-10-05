import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  type FormEvent,
  type KeyboardEvent,
  type UIEvent,
  type ChangeEvent,
} from "react";
import { Info, Phone, Video, Send, Paperclip, ArrowLeft, Loader2, X, AlertCircle } from "lucide-react";
import { useChatStore } from "../store/chatStore";
import { useAuthStore } from "../store/authStore";
import {
  sendMessage as wsSendMessage,
  sendTypingStart,
  sendTypingStop,
  sendMarkSeen,
} from "../hooks/useWebSocket";
import { useMessages } from "../hooks/useMessages";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import { OnlineStatus } from "./OnlineStatus";
import { format, isSameDay } from "date-fns";
import axiosInstance from "../api/axios";
import type { Message } from "../types";

interface ChatWindowProps {
  onBack?: () => void;
}

export function ChatWindow({ onBack }: ChatWindowProps) {
  // ── Store selectors ──
  const conversations = useChatStore((state) => state.conversations);
  const activeConversationId = useChatStore((state) => state.activeConversationId);
  const typingUsers = useChatStore((state) => state.typingUsers);
  const onlineUsers = useChatStore((state) => state.onlineUsers);
  const user = useAuthStore((state) => state.user);

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) ?? null,
    [conversations, activeConversationId]
  );

  // ── Messages ──
  const { messages, isLoading, isLoadingMore, hasMore, loadMore } =
    useMessages(activeConversationId);

  // ── State ──
  const [inputValue, setInputValue] = useState("");
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const prevConvIdRef = useRef<string | null>(null);
  const prevMessagesLenRef = useRef<number>(0);

  const currentTypingUserIds = typingUsers[activeConversationId ?? ""] ?? [];
  const isTyping = currentTypingUserIds.length > 0;

  // Flag to suppress handleScroll during programmatic scrolls
  const isProgrammaticScrollRef = useRef(false);

  // ─────────────────────────────────────────────────────────────────
  // SCROLL TO BOTTOM
  // Only re-runs when messages.length or activeConversationId changes
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || !activeConversationId) return;

    const conversationChanged = prevConvIdRef.current !== activeConversationId;
    const newMessagesArrived = messages.length > prevMessagesLenRef.current;

    prevConvIdRef.current = activeConversationId;
    prevMessagesLenRef.current = messages.length;

    if (messages.length === 0) return;

    const doScroll = () => {
      isProgrammaticScrollRef.current = true;
      container.scrollTop = container.scrollHeight;
      // Release the flag after the browser has processed the scroll event
      requestAnimationFrame(() => {
        isProgrammaticScrollRef.current = false;
      });
    };

    if (conversationChanged) {
      doScroll();
      return;
    }

    if (newMessagesArrived) {
      const distFromBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      if (distFromBottom < 150) {
        doScroll();
      }
    }
  }, [messages.length, activeConversationId]); // ← MUST have dep array to avoid infinite loop

  // Clear replyingTo when switching conversations
  useEffect(() => {
    setReplyingTo(null);
  }, [activeConversationId]);

  // ─────────────────────────────────────────────────────────────────
  // Mark messages as read when conversation opens
  // ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!activeConversationId || !user?.id) return;

    axiosInstance
      .patch(`/conversations/${activeConversationId}/read`)
      .catch(console.error);

    // Mark last unread via WS
    const lastUnread = [...messages]
      .reverse()
      .find((m) => !m.is_read && m.sender_id !== user.id);

    if (lastUnread) {
      sendMarkSeen(activeConversationId, lastUnread.id);
      useChatStore.getState().markConversationAsRead(activeConversationId, user.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId, user?.id]);

  // ─────────────────────────────────────────────────────────────────
  // Infinite scroll — load older messages when at the very top
  // ─────────────────────────────────────────────────────────────────
  const handleScroll = useCallback(
    (e: UIEvent<HTMLDivElement>) => {
      // Skip if this scroll event was triggered by our own programmatic scroll
      if (isProgrammaticScrollRef.current) return;

      const target = e.currentTarget;
      if (target.scrollTop <= 60 && hasMore && !isLoadingMore) {
        const savedScrollHeight = target.scrollHeight;
        loadMore().then(() => {
          requestAnimationFrame(() => {
            if (scrollContainerRef.current) {
              isProgrammaticScrollRef.current = true;
              scrollContainerRef.current.scrollTop =
                scrollContainerRef.current.scrollHeight - savedScrollHeight;
              requestAnimationFrame(() => {
                isProgrammaticScrollRef.current = false;
              });
            }
          });
        });
      }
    },
    [hasMore, isLoadingMore, loadMore]
  );

  // ─────────────────────────────────────────────────────────────────
  // Input
  // ─────────────────────────────────────────────────────────────────
  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);

    // Auto-resize
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        120
      )}px`;
    }

    if (activeConversationId) {
      sendTypingStart(activeConversationId);
      if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = setTimeout(() => {
        sendTypingStop(activeConversationId);
      }, 2000);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend(e);
    }
  };

  const handleSend = async (
    e: FormEvent | KeyboardEvent<HTMLTextAreaElement>
  ) => {
    e.preventDefault();
    const content = inputValue.trim();
    if (!content || !activeConversationId) return;

    const replyToId = replyingTo?.id ?? null;

    // wsSendMessage returns true if WS is OPEN and the message was sent.
    const sentViaWs = wsSendMessage(activeConversationId, content, replyToId);

    if (!sentViaWs) {
      // WS not connected — fall back to REST
      try {
        const res = await axiosInstance.post(
          `/conversations/${activeConversationId}/messages`,
          { content, message_type: "text", reply_to_id: replyToId }
        );
        if (res.data) {
          useChatStore.getState().addMessage(res.data as Message);
        }
      } catch (err) {
        console.error("Failed to send message via REST:", err);
        return;
      }
    }

    setInputValue("");
    setReplyingTo(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    sendTypingStop(activeConversationId);
  };


  // ─────────────────────────────────────────────────────────────────
  // File upload
  // ─────────────────────────────────────────────────────────────────
  const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/gif", "video/mp4", "application/pdf"];
  const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeConversationId) return;

    // ─ Client-side validation ─
    if (!ALLOWED_TYPES.includes(file.type)) {
      setUploadError("Loại file không được hỗ trợ. Chấp nhận: ảnh, video/mp4, PDF.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    if (file.size > MAX_SIZE) {
      setUploadError("File quá lớn. Tối đa 10 MB.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setUploadError(null);
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axiosInstance.post<{
        file_url: string;
        file_name: string;
        file_type: string;
        file_size: number;
      }>("/files/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      // Determine message_type based on MIME
      const msgType = file.type.startsWith("image/") ? "image" : "file";

      await axiosInstance.post(
        `/conversations/${activeConversationId}/messages`,
        { content: res.data.file_url, message_type: msgType, reply_to_id: null }
      );
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Upload thất bại. Vui lòng thử lại.";
      setUploadError(msg);
      console.error("File upload failed:", err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // ─────────────────────────────────────────────────────────────────
  // Empty / placeholder state — no active conversation selected
  // ─────────────────────────────────────────────────────────────────
  if (!activeConversation) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#0f0f17] h-full text-gray-500 select-none">
        <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-4">
          <svg
            className="w-10 h-10 text-gray-600"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-gray-400">
          Chọn một cuộc trò chuyện
        </h2>
        <p className="text-sm mt-2 text-gray-600">
          Chọn từ danh sách hoặc bắt đầu cuộc trò chuyện mới.
        </p>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────
  // Derived info
  // ─────────────────────────────────────────────────────────────────
  const members = activeConversation.members ?? [];

  const otherMember =
    activeConversation.type === "private"
      ? members.find((m) => m.user_id !== user?.id) ?? null
      : null;
  const otherUser = otherMember?.user ?? null;

  const displayName =
    activeConversation.type === "group"
      ? (activeConversation.name ?? "Nhóm chat")
      : (otherUser?.username ?? "Người dùng");

  const avatarLetter = displayName.charAt(0).toUpperCase();
  const isOnline = otherUser ? onlineUsers.includes(otherUser.id) : false;
  const memberCount = members.length;

  // ─────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex-1 flex flex-col h-full bg-[#0f0f17] overflow-hidden">

      {/* ── Header ── */}
      <div className="flex-shrink-0 px-4 py-3 flex items-center justify-between border-b border-white/5 bg-[#13131c]">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              className="md:hidden p-1.5 text-gray-400 hover:text-white transition-colors mr-1"
            >
              <ArrowLeft size={20} />
            </button>
          )}
          <div className="relative flex-shrink-0">
            {otherUser?.avatar_url ? (
              <img
                src={otherUser.avatar_url}
                alt={displayName}
                className="w-10 h-10 rounded-full object-cover"
              />
            ) : (
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white font-semibold">
                {avatarLetter}
              </div>
            )}
            {activeConversation.type === "private" && (
              <OnlineStatus isOnline={isOnline} size="sm" />
            )}
          </div>
          <div>
            <h2 className="text-[15px] font-semibold text-white leading-tight">
              {displayName}
            </h2>
            <p className="text-xs text-gray-500">
              {activeConversation.type === "group"
                ? `${memberCount} thành viên`
                : isOnline
                ? "Đang hoạt động"
                : "Ngoại tuyến"}
            </p>
          </div>
        </div>

        <div className="flex gap-1 text-gray-500">
          <button className="hover:bg-white/5 hover:text-blue-400 p-2 rounded-full transition-all">
            <Phone size={19} />
          </button>
          <button className="hover:bg-white/5 hover:text-blue-400 p-2 rounded-full transition-all">
            <Video size={19} />
          </button>
          <button className="hover:bg-white/5 hover:text-blue-400 p-2 rounded-full transition-all">
            <Info size={19} />
          </button>
        </div>
      </div>

      {/* ── Messages area ── */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 pb-4"
      >
        {/* Spinner for initial load */}
        {isLoading && (
          <div className="flex items-center justify-center py-10">
            <Loader2 size={28} className="animate-spin text-gray-600" />
          </div>
        )}

        {/* Spinner for load-more (top) */}
        {isLoadingMore && (
          <div className="flex justify-center py-3">
            <Loader2 size={18} className="animate-spin text-gray-500" />
          </div>
        )}

        {/* Empty state — loaded but no messages */}
        {!isLoading && messages.length === 0 && (
          <div className="flex items-center justify-center py-16">
            <p className="text-sm text-gray-600">
              Chưa có tin nhắn nào. Hãy bắt đầu cuộc trò chuyện!
            </p>
          </div>
        )}

        {/* Messages list — rendered when not loading AND has data */}
        {!isLoading && messages.length > 0 && (
          <div className="flex flex-col gap-0 pt-4">
            {messages.map((msg, index) => {
              const isOwn = msg.sender_id === user?.id;
              const prevMsg = messages[index - 1];
              const nextMsg = messages[index + 1];

              const showAvatar =
                !isOwn && (!nextMsg || nextMsg.sender_id !== msg.sender_id);

              const isFirstOfDay =
                !prevMsg ||
                !isSameDay(
                  new Date(msg.created_at),
                  new Date(prevMsg.created_at)
                );

              const replyToMessage = msg.reply_to_id
                ? messages.find((m) => m.id === msg.reply_to_id)
                : undefined;

              const senderMember = members.find(
                (m) => m.user_id === msg.sender_id
              );

              return (
                <div key={msg.id}>
                  {isFirstOfDay && (
                    <div className="flex justify-center my-5">
                      <span className="text-xs font-medium text-gray-500 bg-white/5 px-3 py-1 rounded-full">
                        {format(new Date(msg.created_at), "dd/MM/yyyy")}
                      </span>
                    </div>
                  )}
                  <MessageBubble
                    message={msg}
                    isOwn={isOwn}
                    showAvatar={showAvatar}
                    replyToMessage={replyToMessage}
                    senderName={senderMember?.user?.username}
                    isGroup={activeConversation.type === "group"}
                    onReply={setReplyingTo}
                  />
                </div>
              );
            })}

            {/* Typing indicator */}
            {isTyping && (
              <div className="flex justify-start mb-2 mt-1">
                <TypingIndicator typingUserIds={currentTypingUserIds} />
              </div>
            )}

            {/* Invisible scroll anchor — keep at end of messages */}
            <div className="h-px" />
          </div>
        )}
      </div>

      {/* ── Input area ── */}
      <div className="flex-shrink-0 px-4 border-t border-white/5 bg-[#13131c]">
        {/* Reply preview bar */}
        {replyingTo && (
          <div className="flex items-center justify-between border-l-2 border-blue-500 pl-3 pr-2 py-2 mt-3 bg-white/5 rounded-xl">
            <div className="min-w-0">
              <p className="text-xs text-blue-400 font-medium">
                Đang trả lời{" "}
                {replyingTo.sender_id === user?.id ? "chính mình" : "tin nhắn"}
              </p>
              <p className="text-sm text-gray-400 truncate">{replyingTo.content}</p>
            </div>
            <button
              type="button"
              onClick={() => setReplyingTo(null)}
              className="ml-3 flex-shrink-0 text-gray-500 hover:text-white transition-colors p-1 rounded-full hover:bg-white/10"
            >
              <X size={14} />
            </button>
          </div>
        )}

        <form
          onSubmit={handleSend}
          className="flex items-end gap-2 bg-white/5 border border-white/5 rounded-2xl px-3 py-2 my-3"
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept="image/jpeg,image/png,image/gif,video/mp4,application/pdf"
          />
          <button
            type="button"
            onClick={() => {
              setUploadError(null);
              fileInputRef.current?.click();
            }}
            disabled={isUploading}
            title="Đính kèm file"
            className="text-gray-500 hover:text-blue-400 disabled:text-gray-700 disabled:cursor-not-allowed transition-colors p-1.5 flex-shrink-0 relative"
          >
            {isUploading ? (
              <Loader2 size={20} className="animate-spin text-blue-400" />
            ) : (
              <Paperclip size={20} />
            )}
          </button>

          <textarea
            ref={textareaRef}
            id="chat-input"
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={replyingTo ? "Nhập tin nhắn trả lời..." : "Nhập tin nhắn..."}
            className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 text-gray-100 placeholder-gray-600 resize-none py-1.5 text-sm max-h-[120px] leading-relaxed"
            rows={1}
          />

          <button
            id="btn-send"
            type="submit"
            disabled={!inputValue.trim()}
            className="text-blue-500 hover:text-blue-400 disabled:text-gray-700 disabled:cursor-not-allowed transition-all p-1.5 flex-shrink-0"
          >
            <Send size={20} />
          </button>
        </form>
        {/* Upload error banner */}
        {uploadError && (
          <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-2 mx-0">
            <AlertCircle size={13} className="flex-shrink-0" />
            <span className="flex-1">{uploadError}</span>
            <button
              type="button"
              onClick={() => setUploadError(null)}
              className="flex-shrink-0 hover:text-red-300 transition-colors"
            >
              <X size={12} />
            </button>
          </div>
        )}
        <p className="text-xs text-gray-700 pb-2 ml-3">
          Enter để gửi · Shift+Enter để xuống dòng
        </p>
      </div>
    </div>
  );
}
