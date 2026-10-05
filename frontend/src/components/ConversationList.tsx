import { format } from "date-fns";
import type { Conversation } from "../types";
import { cn } from "../lib/utils";
import { OnlineStatus } from "./OnlineStatus";
import { useAuthStore } from "../store/authStore";
import { useChatStore } from "../store/chatStore";

interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
}

function formatTime(dateString: string) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMinutes = Math.floor((now.getTime() - date.getTime()) / 60000);
  
  if (diffMinutes < 1) return "vừa xong";
  if (diffMinutes < 60) return `${diffMinutes}p`;
  if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h`;
  if (diffMinutes < 2880) return "hôm qua";
  return format(date, "dd/MM");
}

export function ConversationList({ conversations, activeId, onSelect }: ConversationListProps) {
  const currentUser = useAuthStore((state) => state.user);
  const onlineUsers = useChatStore((state) => state.onlineUsers);

  // Sort by last message time descending
  const sortedConversations = [...conversations].sort((a, b) => {
    const timeA = a.last_message?.created_at ? new Date(a.last_message.created_at).getTime() : new Date(a.created_at).getTime();
    const timeB = b.last_message?.created_at ? new Date(b.last_message.created_at).getTime() : new Date(b.created_at).getTime();
    return timeB - timeA;
  });

  return (
    <div className="flex-1 overflow-y-auto">
      {sortedConversations.map((conv) => {
        // Find the other participant in private chats
        const otherUser =
          conv.type === "private"
            ? conv.members.find((m) => m.user.id !== currentUser?.id)?.user
            : null;

        const displayName = conv.type === "group" ? conv.name : (otherUser?.username || "Unknown");
        const isOnline = otherUser ? onlineUsers.includes(otherUser.id) : false;
        
        let lastMessageText = conv.last_message?.content || "No messages yet";
        if (conv.last_message?.sender_id === currentUser?.id) {
          lastMessageText = `You: ${lastMessageText}`;
        }
        
        if (lastMessageText.length > 30) {
          lastMessageText = lastMessageText.substring(0, 30) + "...";
        }
        
        const unreadCount = conv.unread_count || 0;
        const isUnread = unreadCount > 0;

        return (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={cn(
              "flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-800 transition-colors mx-2 rounded-xl mb-1",
              activeId === conv.id ? "bg-gray-800" : ""
            )}
          >
            {/* Avatar */}
            <div className="relative flex-shrink-0">
              <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white font-semibold text-lg">
                {displayName ? displayName.charAt(0).toUpperCase() : "?"}
              </div>
              {conv.type === "private" && <OnlineStatus isOnline={isOnline} />}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex justify-between items-baseline mb-0.5">
                <h3 className={cn("text-[15px] truncate", isUnread ? "font-semibold text-white" : "font-medium text-gray-200")}>
                  {displayName}
                </h3>
                {conv.last_message && (
                  <span className={cn("text-xs flex-shrink-0 ml-2", isUnread ? "text-blue-400 font-semibold" : "text-gray-400")}>
                    {formatTime(conv.last_message.created_at)}
                  </span>
                )}
              </div>
              <div className="flex justify-between items-center">
                <p className={cn("text-[14px] truncate", isUnread ? "font-semibold text-gray-300" : "text-gray-400")}>
                  {lastMessageText}
                </p>
                {isUnread && (
                  <div className="bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ml-2 min-w-[20px] text-center">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
      
      {conversations.length === 0 && (
        <div className="p-4 text-center text-gray-400 text-sm">
          No conversations yet.
        </div>
      )}
    </div>
  );
}
