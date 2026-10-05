import { useState, useEffect, useRef, useCallback } from "react";
import {
  Search,
  X,
  LogOut,
  Plus,
  Users,
  MessageCircle,
  UserPlus,
  UserCheck,
  Clock,
  Check,
  XCircle,
  Loader2,
  BarChart3,
} from "lucide-react";
import { ConversationList } from "./ConversationList";
import { useChatStore } from "../store/chatStore";
import { useAuthStore } from "../store/authStore";
import { useConversations } from "../hooks/useConversations";
import { useNavigate } from "react-router-dom";
import axiosInstance from "../api/axios";
import type { User, Conversation, Friendship } from "../types";
import { cn } from "../lib/utils";

type SidebarTab = "chats" | "friends";

interface SidebarProps {
  /** Called when a conversation is selected (for mobile: switch view) */
  onConversationSelect?: () => void;
}

/** Friendship status for a specific user in search results */
interface UserWithFriendship extends User {
  friendshipStatus?: "none" | "pending_sent" | "pending_received" | "accepted";
  friendshipId?: string;
}

export function Sidebar({ onConversationSelect }: SidebarProps) {
  const conversations = useChatStore((state) => state.conversations);
  const activeConversationId = useChatStore(
    (state) => state.activeConversationId
  );
  const setActiveConversation = useChatStore(
    (state) => state.setActiveConversation
  );
  const setConversations = useChatStore((state) => state.setConversations);
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  const { isLoading } = useConversations();

  // ── Tab state ──
  const [activeTab, setActiveTab] = useState<SidebarTab>("chats");

  // ── Search state ──
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<UserWithFriendship[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Friend request states ──
  const [friends, setFriends] = useState<Friendship[]>([]);
  const [pendingRequests, setPendingRequests] = useState<Friendship[]>([]);
  const [friendsLoading, setFriendsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // ── Group create modal state ──
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [groupName, setGroupName] = useState("");
  const [groupSearchQ, setGroupSearchQ] = useState("");
  const [groupSearchResults, setGroupSearchResults] = useState<User[]>([]);
  const [selectedMembers, setSelectedMembers] = useState<User[]>([]);
  const [groupCreating, setGroupCreating] = useState(false);

  // ── Load friends & pending requests ──
  const loadFriends = useCallback(async () => {
    setFriendsLoading(true);
    try {
      const [friendsRes, pendingRes] = await Promise.all([
        axiosInstance.get<Friendship[]>("/friends"),
        axiosInstance.get<Friendship[]>("/friends/pending"),
      ]);
      setFriends(friendsRes.data);
      setPendingRequests(pendingRes.data);
    } catch (err) {
      console.error("Failed to load friends", err);
    } finally {
      setFriendsLoading(false);
    }
  }, []);

  // Load friends when tab switches to friends
  useEffect(() => {
    if (activeTab === "friends") {
      loadFriends();
    }
  }, [activeTab, loadFriends]);

  // ── Search users with debounce 300ms ──
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      setSearchLoading(false);
      return;
    }

    setIsSearching(true);
    setSearchLoading(true);

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);

    searchTimeoutRef.current = setTimeout(async () => {
      try {
        // Fetch search results
        const usersRes = await axiosInstance.get<User[]>(
          `/users/search?q=${encodeURIComponent(searchQuery.trim())}`
        );

        // Fetch current friendships to determine status for each user
        const [friendsRes, pendingRes] = await Promise.all([
          axiosInstance.get<Friendship[]>("/friends"),
          axiosInstance.get<Friendship[]>("/friends/pending"),
        ]);

        const enriched: UserWithFriendship[] = usersRes.data.map((u) => {
          // Check if already friends
          const acceptedFriend = friendsRes.data.find(
            (f) =>
              f.status === "accepted" &&
              (f.requester_id === u.id || f.addressee_id === u.id)
          );
          if (acceptedFriend) {
            return {
              ...u,
              friendshipStatus: "accepted" as const,
              friendshipId: acceptedFriend.id,
            };
          }

          // Check if pending (I sent)
          const pendingSent = friendsRes.data.find(
            (f) =>
              f.status === "pending" &&
              f.requester_id === user?.id &&
              f.addressee_id === u.id
          );
          // Also check in the broader pending list or from /friends response
          // The /friends endpoint returns accepted only, so we need to check differently
          // Let's search all friendships that are pending where I am the requester
          // Actually, the /friends returns accepted, and /friends/pending returns incoming.
          // For "sent" pending, we need to check via the search results.
          // Let's try a different approach - just try to send and handle 409

          // Check if there's a pending request I received
          const pendingReceived = pendingRes.data.find(
            (f) =>
              f.status === "pending" &&
              (f.requester_id === u.id)
          );
          if (pendingReceived) {
            return {
              ...u,
              friendshipStatus: "pending_received" as const,
              friendshipId: pendingReceived.id,
            };
          }

          if (pendingSent) {
            return {
              ...u,
              friendshipStatus: "pending_sent" as const,
              friendshipId: pendingSent.id,
            };
          }

          return { ...u, friendshipStatus: "none" as const };
        });

        setSearchResults(enriched);
      } catch (err) {
        console.error("Search error", err);
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 300);

    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, [searchQuery, user?.id]);

  // ── Search inside group modal ──
  useEffect(() => {
    if (!groupSearchQ.trim()) {
      setGroupSearchResults([]);
      return;
    }
    const t = setTimeout(() => {
      axiosInstance
        .get<User[]>(
          `/users/search?q=${encodeURIComponent(groupSearchQ.trim())}`
        )
        .then((res) => setGroupSearchResults(res.data))
        .catch(console.error);
    }, 300);
    return () => clearTimeout(t);
  }, [groupSearchQ]);

  // ── Actions ──
  const handleSendFriendRequest = async (targetUser: UserWithFriendship) => {
    setActionLoading(targetUser.id);
    try {
      await axiosInstance.post("/friends/request", {
        addressee_id: targetUser.id,
      });
      // Update the search result to show "pending_sent"
      setSearchResults((prev) =>
        prev.map((u) =>
          u.id === targetUser.id
            ? { ...u, friendshipStatus: "pending_sent" as const }
            : u
        )
      );
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Gửi lời mời thất bại";
      // If already pending or friends, update UI accordingly
      if (detail === "Friend request already pending") {
        setSearchResults((prev) =>
          prev.map((u) =>
            u.id === targetUser.id
              ? { ...u, friendshipStatus: "pending_sent" as const }
              : u
          )
        );
      } else if (detail === "Already friends") {
        setSearchResults((prev) =>
          prev.map((u) =>
            u.id === targetUser.id
              ? { ...u, friendshipStatus: "accepted" as const }
              : u
          )
        );
      }
      console.error("Send friend request failed:", detail);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAcceptRequest = async (friendshipId: string) => {
    setActionLoading(friendshipId);
    try {
      await axiosInstance.patch(`/friends/${friendshipId}/accept`);
      await loadFriends();
    } catch (err) {
      console.error("Accept failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectRequest = async (friendshipId: string) => {
    setActionLoading(friendshipId);
    try {
      await axiosInstance.delete(`/friends/${friendshipId}`);
      await loadFriends();
    } catch (err) {
      console.error("Reject failed", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStartPrivateChat = async (targetUser: User) => {
    try {
      const res = await axiosInstance.post<Conversation>(
        "/conversations/private",
        {
          user_id: targetUser.id,
        }
      );
      const newConv = res.data;
      if (!conversations.some((c) => c.id === newConv.id)) {
        setConversations([newConv, ...conversations]);
      }
      setActiveConversation(newConv.id);
      navigate(`/chat/${newConv.id}`);
      setSearchQuery("");
      setSearchResults([]);
      setIsSearching(false);
      setActiveTab("chats");
      onConversationSelect?.();
    } catch (err) {
      console.error("Failed to start chat", err);
    }
  };

  const handleCreateGroup = async () => {
    if (!groupName.trim() || selectedMembers.length === 0) return;
    setGroupCreating(true);
    try {
      const res = await axiosInstance.post<Conversation>(
        "/conversations/group",
        {
          name: groupName.trim(),
          member_ids: selectedMembers.map((u) => u.id),
        }
      );
      const newConv = res.data;
      setConversations([newConv, ...conversations]);
      setActiveConversation(newConv.id);
      navigate(`/chat/${newConv.id}`);
      setShowGroupModal(false);
      setGroupName("");
      setSelectedMembers([]);
      setGroupSearchQ("");
      onConversationSelect?.();
    } catch (err) {
      console.error("Failed to create group", err);
    } finally {
      setGroupCreating(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleSelectConversation = (id: string) => {
    setActiveConversation(id);
    navigate(`/chat/${id}`);
    onConversationSelect?.();
  };

  const avatarLetter = user?.username?.charAt(0).toUpperCase() ?? "?";

  // ── Get friend's user info from Friendship object ──
  const getFriendUser = (friendship: Friendship): User | null => {
    if (!user) return null;
    if (friendship.requester_id === user.id) {
      return friendship.addressee ?? null;
    }
    return friendship.requester ?? null;
  };

  return (
    <>
      <div className="w-full md:w-80 h-full bg-[#16161e] border-r border-white/5 flex flex-col">
        {/* ── Header ── */}
        <div className="px-4 pt-5 pb-3 flex items-center justify-between">
          <h1 className="text-xl font-bold text-white tracking-tight">
            ChatApp
          </h1>
          <div className="flex items-center gap-1.5">
            <button
              id="btn-analytics"
              onClick={() => navigate("/analytics")}
              className="p-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 hover:text-indigo-300 border border-indigo-500/20 rounded-full transition-all"
              title="Streaming Analytics Dashboard"
            >
              <BarChart3 size={17} />
            </button>
            <button
              id="btn-new-group"
              onClick={() => setShowGroupModal(true)}
              className="p-2 bg-white/5 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-all"
              title="Tạo nhóm chat mới"
            >
              <Plus size={18} />
            </button>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className="flex border-b border-white/5 mx-4 mb-1">
          <button
            onClick={() => { setActiveTab("chats"); setSearchQuery(""); setIsSearching(false); }}
            className={cn(
              "flex-1 py-2.5 text-xs font-semibold uppercase tracking-wider transition-all duration-200 border-b-2",
              activeTab === "chats"
                ? "text-blue-400 border-blue-500"
                : "text-gray-500 border-transparent hover:text-gray-300"
            )}
          >
            <div className="flex items-center justify-center gap-1.5">
              <MessageCircle size={14} />
              Tin nhắn
            </div>
          </button>
          <button
            onClick={() => { setActiveTab("friends"); setSearchQuery(""); setIsSearching(false); }}
            className={cn(
              "flex-1 py-2.5 text-xs font-semibold uppercase tracking-wider transition-all duration-200 border-b-2 relative",
              activeTab === "friends"
                ? "text-blue-400 border-blue-500"
                : "text-gray-500 border-transparent hover:text-gray-300"
            )}
          >
            <div className="flex items-center justify-center gap-1.5">
              <Users size={14} />
              Bạn bè
              {pendingRequests.length > 0 && (
                <span className="ml-1 bg-red-500 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                  {pendingRequests.length}
                </span>
              )}
            </div>
          </button>
        </div>

        {/* ── Search ── */}
        <div className="px-4 pb-3">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <Search size={15} className="text-gray-500" />
            </div>
            <input
              id="sidebar-search"
              type="text"
              className="block w-full pl-9 pr-8 py-2.5 rounded-xl bg-white/5 border border-white/5 text-gray-300 placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/40 focus:bg-blue-500/5 transition-all"
              placeholder="Tìm kiếm người dùng..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-white transition-colors"
                onClick={() => {
                  setSearchQuery("");
                  setIsSearching(false);
                }}
              >
                <X size={15} />
              </button>
            )}
          </div>
        </div>

        {/* ── Main area ── */}
        <div className="flex-1 overflow-y-auto">
          {/* ── SEARCH RESULTS ── */}
          {isSearching ? (
            <div className="px-3">
              <p className="px-2 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Kết quả tìm kiếm
              </p>
              {searchLoading ? (
                <div className="text-center py-6 text-gray-500 text-sm flex items-center justify-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  Đang tìm...
                </div>
              ) : searchResults.length === 0 ? (
                <div className="text-center py-6 text-gray-500 text-sm">
                  Không tìm thấy ai.
                </div>
              ) : (
                searchResults.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center gap-3 p-3 hover:bg-white/5 transition-colors rounded-xl mb-1"
                  >
                    {/* Avatar */}
                    <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                      {u.username.charAt(0).toUpperCase()}
                    </div>

                    {/* User info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-200 truncate">
                        {u.username}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        {u.email}
                      </p>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {u.friendshipStatus === "none" && (
                        <button
                          onClick={() => handleSendFriendRequest(u)}
                          disabled={actionLoading === u.id}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 rounded-lg transition-all disabled:opacity-50"
                          title="Gửi lời mời kết bạn"
                        >
                          {actionLoading === u.id ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <UserPlus size={12} />
                          )}
                          Kết bạn
                        </button>
                      )}

                      {u.friendshipStatus === "pending_sent" && (
                        <span className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                          <Clock size={12} />
                          Đã gửi
                        </span>
                      )}

                      {u.friendshipStatus === "pending_received" && (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() =>
                              u.friendshipId &&
                              handleAcceptRequest(u.friendshipId)
                            }
                            disabled={actionLoading === u.friendshipId}
                            className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-green-400 bg-green-500/10 hover:bg-green-500/20 border border-green-500/20 rounded-lg transition-all disabled:opacity-50"
                            title="Chấp nhận"
                          >
                            <Check size={12} />
                          </button>
                          <button
                            onClick={() =>
                              u.friendshipId &&
                              handleRejectRequest(u.friendshipId)
                            }
                            disabled={actionLoading === u.friendshipId}
                            className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-all disabled:opacity-50"
                            title="Từ chối"
                          >
                            <XCircle size={12} />
                          </button>
                        </div>
                      )}

                      {u.friendshipStatus === "accepted" && (
                        <button
                          onClick={() => handleStartPrivateChat(u)}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 rounded-lg transition-all"
                          title="Nhắn tin"
                        >
                          <MessageCircle size={12} />
                          Nhắn tin
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : activeTab === "chats" ? (
            /* ── CHATS TAB ── */
            <>
              {isLoading && conversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-600 text-sm gap-2">
                  <div className="w-6 h-6 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
                  Đang tải...
                </div>
              ) : (
                <ConversationList
                  conversations={conversations}
                  activeId={activeConversationId}
                  onSelect={handleSelectConversation}
                />
              )}
            </>
          ) : (
            /* ── FRIENDS TAB ── */
            <div className="px-3">
              {friendsLoading ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-600 text-sm gap-2">
                  <Loader2 size={20} className="animate-spin" />
                  Đang tải...
                </div>
              ) : (
                <>
                  {/* Pending requests */}
                  {pendingRequests.length > 0 && (
                    <div className="mb-4">
                      <p className="px-2 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                        Lời mời kết bạn ({pendingRequests.length})
                      </p>
                      {pendingRequests.map((req) => {
                        const reqUser = getFriendUser(req);
                        if (!reqUser) return null;
                        return (
                          <div
                            key={req.id}
                            className="flex items-center gap-3 p-3 hover:bg-white/5 transition-colors rounded-xl mb-1"
                          >
                            <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-pink-600 rounded-full flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                              {reqUser.username.charAt(0).toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-200 truncate">
                                {reqUser.username}
                              </p>
                              <p className="text-xs text-gray-500">
                                Muốn kết bạn với bạn
                              </p>
                            </div>
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              <button
                                onClick={() => handleAcceptRequest(req.id)}
                                disabled={actionLoading === req.id}
                                className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-green-400 bg-green-500/10 hover:bg-green-500/20 border border-green-500/20 rounded-lg transition-all disabled:opacity-50"
                              >
                                {actionLoading === req.id ? (
                                  <Loader2
                                    size={12}
                                    className="animate-spin"
                                  />
                                ) : (
                                  <Check size={12} />
                                )}
                                Chấp nhận
                              </button>
                              <button
                                onClick={() => handleRejectRequest(req.id)}
                                disabled={actionLoading === req.id}
                                className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-400 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg transition-all disabled:opacity-50"
                              >
                                <XCircle size={12} />
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Accepted friends list */}
                  <p className="px-2 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Bạn bè ({friends.length})
                  </p>
                  {friends.length === 0 ? (
                    <div className="text-center py-10 text-gray-600 text-sm">
                      <UserCheck
                        size={32}
                        className="mx-auto mb-3 text-gray-700"
                      />
                      <p>Chưa có bạn bè nào.</p>
                      <p className="text-xs text-gray-700 mt-1">
                        Tìm kiếm và gửi lời mời kết bạn!
                      </p>
                    </div>
                  ) : (
                    friends.map((friendship) => {
                      const friendUser = getFriendUser(friendship);
                      if (!friendUser) return null;
                      return (
                        <div
                          key={friendship.id}
                          className="flex items-center gap-3 p-3 hover:bg-white/5 transition-colors rounded-xl mb-1 cursor-pointer"
                          onClick={() =>
                            handleStartPrivateChat(friendUser as User)
                          }
                        >
                          <div className="relative flex-shrink-0">
                            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
                              {friendUser.username.charAt(0).toUpperCase()}
                            </div>
                            {friendUser.is_online && (
                              <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-500 rounded-full border-2 border-[#16161e]" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-200 truncate">
                              {friendUser.username}
                            </p>
                            <p className="text-xs text-gray-500">
                              {friendUser.is_online
                                ? "Đang hoạt động"
                                : "Ngoại tuyến"}
                            </p>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleStartPrivateChat(friendUser as User);
                            }}
                            className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 rounded-lg transition-all flex-shrink-0"
                            title="Nhắn tin"
                          >
                            <MessageCircle size={12} />
                            Nhắn tin
                          </button>
                        </div>
                      );
                    })
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* ── User info / footer ── */}
        <div className="px-4 py-3 border-t border-white/5 flex items-center gap-3">
          <div className="relative flex-shrink-0">
            <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white font-semibold text-sm">
              {avatarLetter}
            </div>
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-500 rounded-full border-2 border-[#16161e]" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white truncate">
              {user?.username}
            </p>
            <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          </div>
          <button
            id="btn-logout"
            onClick={handleLogout}
            className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-full transition-all"
            title="Đăng xuất"
          >
            <LogOut size={17} />
          </button>
        </div>
      </div>

      {/* ── Create Group Modal ── */}
      {showGroupModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-[#1e1e2a] border border-white/10 rounded-2xl w-full max-w-sm shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
              <div className="flex items-center gap-2">
                <Users size={18} className="text-blue-400" />
                <h2 className="text-white font-semibold text-base">
                  Tạo nhóm mới
                </h2>
              </div>
              <button
                onClick={() => {
                  setShowGroupModal(false);
                  setGroupName("");
                  setSelectedMembers([]);
                  setGroupSearchQ("");
                }}
                className="text-gray-500 hover:text-white transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">
                  Tên nhóm
                </label>
                <input
                  type="text"
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder="Nhập tên nhóm..."
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500/50 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1.5 uppercase tracking-wider">
                  Thêm thành viên
                </label>
                <input
                  type="text"
                  value={groupSearchQ}
                  onChange={(e) => setGroupSearchQ(e.target.value)}
                  placeholder="Tìm người dùng..."
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500/50 transition-all"
                />
                {groupSearchResults.length > 0 && (
                  <div className="mt-2 max-h-32 overflow-y-auto rounded-xl border border-white/5 bg-white/5">
                    {groupSearchResults
                      .filter((u) => u.id !== user?.id)
                      .map((u) => (
                        <div
                          key={u.id}
                          onClick={() => {
                            if (
                              !selectedMembers.find((m) => m.id === u.id)
                            ) {
                              setSelectedMembers((prev) => [...prev, u]);
                            }
                            setGroupSearchQ("");
                            setGroupSearchResults([]);
                          }}
                          className={cn(
                            "flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-white/5 transition-colors text-sm",
                            selectedMembers.find((m) => m.id === u.id) &&
                              "opacity-40 cursor-not-allowed"
                          )}
                        >
                          <div className="w-7 h-7 bg-indigo-600 rounded-full flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
                            {u.username.charAt(0).toUpperCase()}
                          </div>
                          <span className="text-gray-200">{u.username}</span>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              {/* Selected members chips */}
              {selectedMembers.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {selectedMembers.map((m) => (
                    <span
                      key={m.id}
                      className="flex items-center gap-1 bg-blue-600/20 border border-blue-500/30 text-blue-300 text-xs px-2.5 py-1 rounded-full"
                    >
                      {m.username}
                      <button
                        onClick={() =>
                          setSelectedMembers((prev) =>
                            prev.filter((x) => x.id !== m.id)
                          )
                        }
                        className="hover:text-white transition-colors"
                      >
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              <button
                onClick={handleCreateGroup}
                disabled={
                  !groupName.trim() ||
                  selectedMembers.length === 0 ||
                  groupCreating
                }
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:opacity-90"
              >
                {groupCreating ? "Đang tạo..." : "Tạo nhóm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
