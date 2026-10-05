// ============================================================
// Core domain types — mirrors backend response shapes exactly
// ============================================================

export interface User {
  id: string;
  email: string;
  username: string;
  avatar_url?: string | null;
  is_online: boolean;
  last_seen?: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  content: string;
  message_type: string; // "text" | "image" | "file"
  reply_to_id?: string | null;
  is_deleted: boolean;
  created_at: string;
  is_read?: boolean;
}

export interface ConversationMember {
  id: string;
  conversation_id: string;
  user_id: string;
  role: string; // "admin" | "member"
  last_read_at?: string | null;
  joined_at: string;
  user: User;
}

export interface Conversation {
  id: string;
  type: "private" | "group";
  name?: string | null;
  avatar_url?: string | null;
  last_message?: Message | null;
  unread_count: number;
  members: ConversationMember[];
  created_at: string;
}

export interface Friendship {
  id: string;
  requester_id: string;
  addressee_id: string;
  status: "pending" | "accepted" | "rejected";
  created_at: string;
  requester: User;
  addressee: User;
}

export interface Attachment {
  id: string;
  message_id: string;
  file_url: string;
  file_name: string;
  file_type: string;
  file_size: number;
}

// Auth response shapes
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
