import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  RefreshCw,
  Users,
  MessageSquare,
  Zap,
  TrendingUp,
  Database,
  Layers,
  Pause,
  Play,
  Clock,
  Sparkles,
  Info
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from "recharts";
import {
  getMessagesPerMinute,
  getActiveUsersPerMinute,
  getMessagesPerConversation,
  type MessagePerMinuteMetric,
  type ActiveUsersMetric,
  type ConversationMetric
} from "../api/analytics";

export function AnalyticsPage() {
  const navigate = useNavigate();

  const [messagesPerMin, setMessagesPerMin] = useState<MessagePerMinuteMetric[]>([]);
  const [activeUsersPerMin, setActiveUsersPerMin] = useState<ActiveUsersMetric[]>([]);
  const [convMetrics, setConvMetrics] = useState<ConversationMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
  const [refreshCountdown, setRefreshCountdown] = useState(5);

  const fetchAnalytics = useCallback(async () => {
    try {
      const [msgData, userData, convData] = await Promise.all([
        getMessagesPerMinute(20),
        getActiveUsersPerMinute(20),
        // Look back 20 minutes, return top 10 conversations
        getMessagesPerConversation(20, 10),
      ]);

      // Reverse so chronological order (left to right)
      setMessagesPerMin([...msgData].reverse());
      setActiveUsersPerMin([...userData].reverse());
      setConvMetrics(convData);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error("Failed to fetch analytics data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // 5s Polling loop
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      setRefreshCountdown((prev) => {
        if (prev <= 1) {
          fetchAnalytics();
          return 5;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, fetchAnalytics]);

  // Format time for charts (24-hour format)
  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const d = new Date(isoString);
      const isToday = d.toDateString() === new Date().toDateString();
      const timeStr = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
      return isToday ? timeStr : `${d.getDate()}/${d.getMonth() + 1} ${timeStr}`;
    } catch {
      return isoString;
    }
  };

  // Compute KPI metrics
  const latestMsgCount = messagesPerMin.length > 0 ? messagesPerMin[messagesPerMin.length - 1].message_count : 0;
  const latestActiveUsers = activeUsersPerMin.length > 0 ? activeUsersPerMin[activeUsersPerMin.length - 1].active_users : 0;
  const peakMsgCount = messagesPerMin.length > 0 ? Math.max(...messagesPerMin.map(m => m.message_count)) : 0;
  const totalTrackedConversations = new Set(convMetrics.map(c => c.conversation_id)).size;

  // Chart data formatting
  const messageChartData = messagesPerMin.map((m) => ({
    time: formatTime(m.window_start),
    messages: m.message_count,
    window: `${formatTime(m.window_start)} - ${formatTime(m.window_end)}`,
  }));

  const userChartData = activeUsersPerMin.map((u) => ({
    time: formatTime(u.window_start),
    users: u.active_users,
    window: `${formatTime(u.window_start)} - ${formatTime(u.window_end)}`,
  }));

  // Top conversations — already aggregated by the API over the last 20 minutes
  const topConversations = convMetrics
    .map((c) => ({
      conversationId: c.conversation_id.substring(0, 8) + "...",
      fullId: c.conversation_id,
      count: Number(c.message_count),
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);

  return (
    <div className="min-h-screen bg-[#0d0d15] text-slate-100 flex flex-col font-sans">
      {/* ── Top Navigation & Live Header ── */}
      <header className="border-b border-white/10 bg-[#131320]/80 backdrop-blur-md sticky top-0 z-30 px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/chat")}
              className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 hover:text-white transition-all flex items-center gap-2 text-sm font-medium"
              title="Về giao diện Chat"
            >
              <ArrowLeft size={16} />
              <span>Về Chat</span>
            </button>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
                  Real-Time Streaming Analytics
                </h1>
                <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Pipeline: FastAPI WebSocket → Kafka (chat-events) → Spark Structured Streaming (1m tumbling) → PostgreSQL
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end md:self-auto">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                autoRefresh
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                  : "bg-white/5 border-white/10 text-gray-400 hover:text-gray-200"
              }`}
            >
              {autoRefresh ? <Pause size={14} /> : <Play size={14} />}
              <span>Auto-refresh {autoRefresh ? `(${refreshCountdown}s)` : "Tắt"}</span>
            </button>

            <button
              onClick={() => fetchAnalytics()}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 hover:text-white transition-all"
              title="Làm mới ngay"
            >
              <RefreshCw size={16} className={loading ? "animate-spin text-blue-400" : ""} />
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Dashboard Body ── */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Architecture Pipeline Pill Badges */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-white/[0.03] border border-white/5">
            <div className="p-2 rounded-xl bg-orange-500/10 text-orange-400">
              <Zap size={18} />
            </div>
            <div>
              <div className="text-xs text-gray-400">Broker</div>
              <div className="text-sm font-semibold text-gray-200">Kafka KRaft</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-white/[0.03] border border-white/5">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
              <Layers size={18} />
            </div>
            <div>
              <div className="text-xs text-gray-400">Processing</div>
              <div className="text-sm font-semibold text-gray-200">Spark 1m Window</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-white/[0.03] border border-white/5">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Database size={18} />
            </div>
            <div>
              <div className="text-xs text-gray-400">Storage</div>
              <div className="text-sm font-semibold text-gray-200">PostgreSQL Analytics</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3.5 rounded-2xl bg-white/[0.03] border border-white/5">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
              <Clock size={18} />
            </div>
            <div>
              <div className="text-xs text-gray-400">Watermark SLA</div>
              <div className="text-sm font-semibold text-gray-200">30s Late Handling</div>
            </div>
          </div>
        </div>

        {/* ── KPI Metric Cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1 */}
          <div className="p-5 rounded-2xl bg-gradient-to-b from-[#181828] to-[#121220] border border-white/10 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-blue-500 to-indigo-500" />
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Tin nhắn (Cửa sổ gần nhất)</span>
              <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
                <MessageSquare size={18} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">{latestMsgCount}</span>
              <span className="text-xs text-gray-400">msgs / min</span>
            </div>
            <div className="mt-2 text-xs text-gray-500 flex items-center gap-1">
              <TrendingUp size={12} className="text-emerald-400" />
              <span>Đỉnh cao: {peakMsgCount} msgs/min</span>
            </div>
            <div className="mt-1 text-xs text-amber-500/70 italic">* Cửa sổ hiện tại chưa kết thúc — số còn tăng</div>
          </div>

          {/* Card 2 */}
          <div className="p-5 rounded-2xl bg-gradient-to-b from-[#181828] to-[#121220] border border-white/10 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-purple-500 to-pink-500" />
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Người dùng hoạt động</span>
              <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                <Users size={18} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">{latestActiveUsers}</span>
              <span className="text-xs text-gray-400">active users / min</span>
            </div>
            <div className="mt-2 text-xs text-gray-500 flex items-center gap-1">
              <span>approx_count_distinct (HyperLogLog, ~2% sai số)</span>
            </div>
          </div>

          {/* Card 3 */}
          <div className="p-5 rounded-2xl bg-gradient-to-b from-[#181828] to-[#121220] border border-white/10 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-emerald-500 to-teal-500" />
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Hội thoại đang hoạt động</span>
              <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
                <Activity size={18} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white tracking-tight">{totalTrackedConversations}</span>
              <span className="text-xs text-gray-400">phòng chat</span>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Phân vùng theo partition key: conversation_id
            </div>
          </div>

          {/* Card 4 */}
          <div className="p-5 rounded-2xl bg-gradient-to-b from-[#181828] to-[#121220] border border-white/10 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-amber-500 to-orange-500" />
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Cập nhật lần cuối</span>
              <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
                <Clock size={18} />
              </div>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white tracking-tight">
                {lastRefreshed.toLocaleTimeString("vi-VN", { hour12: false })}
              </span>
            </div>
            <div className="mt-2 text-xs text-gray-500">
              Tần suất poll: 5s / lần
            </div>
          </div>
        </div>

        {/* ── Charts Grid ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Chart 1: Messages Throughput */}
          <div className="p-6 rounded-2xl bg-[#141424] border border-white/10 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <TrendingUp size={18} className="text-blue-400" />
                  Lưu lượng tin nhắn (Messages / Minute)
                </h3>
                <p className="text-xs text-gray-400">Thống kê theo cửa sổ Tumbling 1 phút</p>
              </div>
              <span className="text-xs bg-blue-500/10 text-blue-400 px-2.5 py-1 rounded-lg border border-blue-500/20">
                stream_messages_per_minute
              </span>
            </div>

            <div className="h-64 w-full">
              {messageChartData.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm gap-2">
                  <Info size={24} />
                  <span>Chưa có dữ liệu từ Spark. Hãy gửi tin nhắn hoặc chạy producer_test.py.</span>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={messageChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="msgGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
                    <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
                    <YAxis stroke="#6b7280" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e1e30", borderColor: "#3b82f6", borderRadius: "8px" }}
                      labelStyle={{ color: "#9ca3af" }}
                    />
                    <Area
                      type="monotone"
                      dataKey="messages"
                      name="Số tin nhắn"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#msgGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Chart 2: Active Users */}
          <div className="p-6 rounded-2xl bg-[#141424] border border-white/10 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <Users size={18} className="text-purple-400" />
                  Người dùng hoạt động đồng thời (Active Users)
                </h3>
                <p className="text-xs text-gray-400">Số user phân biệt gửi tin nhắn trong mỗi cửa sổ 1m</p>
              </div>
              <span className="text-xs bg-purple-500/10 text-purple-400 px-2.5 py-1 rounded-lg border border-purple-500/20">
                stream_active_users_per_minute
              </span>
            </div>

            <div className="h-64 w-full">
              {userChartData.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm gap-2">
                  <Info size={24} />
                  <span>Chưa có dữ liệu từ Spark.</span>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={userChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#252538" />
                    <XAxis dataKey="time" stroke="#6b7280" fontSize={11} />
                    <YAxis stroke="#6b7280" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e1e30", borderColor: "#a855f7", borderRadius: "8px" }}
                      labelStyle={{ color: "#9ca3af" }}
                    />
                    <Bar dataKey="users" name="Active Users" fill="#a855f7" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </div>

        {/* ── Bottom Section: Top Active Conversations & Micro-batch History ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Top Conversations Card */}
          <div className="p-6 rounded-2xl bg-[#141424] border border-white/10 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <Sparkles size={18} className="text-amber-400" />
              Hội thoại sôi nổi nhất
            </h3>
            <p className="text-xs text-gray-400">Tổng tin nhắn theo Conversation ID — 20 phút gần nhất</p>

            <div className="space-y-3 mt-4">
              {topConversations.length === 0 ? (
                <p className="text-xs text-gray-500 italic py-4">Chưa có thông tin hội thoại</p>
              ) : (
                topConversations.map((c, i) => (
                  <div key={c.fullId} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono text-gray-300">#{i + 1} {c.conversationId}</span>
                      <span className="text-emerald-400 font-semibold">{c.count} msgs</span>
                    </div>
                    <div className="w-full bg-white/5 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, (c.count / (topConversations[0]?.count || 1)) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Micro-batch Activity Feed Table */}
          <div className="lg:col-span-2 p-6 rounded-2xl bg-[#141424] border border-white/10 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Database size={18} className="text-emerald-400" />
                Lịch sử Micro-batch (PostgreSQL Analytics Tables)
              </h3>
              <span className="text-xs text-gray-400">{messagesPerMin.length} records</span>
            </div>

            <div className="overflow-x-auto max-h-64 overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-white/5 text-gray-400 uppercase tracking-wider sticky top-0">
                  <tr>
                    <th className="py-2.5 px-3">Cửa sổ bắt đầu</th>
                    <th className="py-2.5 px-3">Cửa sổ kết thúc</th>
                    <th className="py-2.5 px-3 text-right">Tin nhắn</th>
                    <th className="py-2.5 px-3 text-right">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-gray-300">
                  {messagesPerMin.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-6 text-center text-gray-500">
                        Chưa có dữ liệu nào được ghi vào bảng stream_messages_per_minute.
                      </td>
                    </tr>
                  ) : (
                    messagesPerMin.slice().reverse().map((row, idx) => (
                      <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                        <td className="py-2 px-3 font-mono">{formatTime(row.window_start)}</td>
                        <td className="py-2 px-3 font-mono">{formatTime(row.window_end)}</td>
                        <td className="py-2 px-3 text-right font-semibold text-blue-400">{row.message_count}</td>
                        <td className="py-2 px-3 text-right">
                          <span className="inline-block px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            UPSERTED
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* ── Instruction Banner for Testing ── */}
        <div className="p-4 rounded-2xl bg-indigo-950/30 border border-indigo-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs text-indigo-200">
          <div className="flex items-center gap-2">
            <Info size={16} className="text-indigo-400 flex-shrink-0" />
            <span>
              <strong>Thử nghiệm Real-time Streaming:</strong> Chạy script mô phỏng traffic để bơm dữ liệu vào Kafka: <code className="bg-black/40 px-2 py-0.5 rounded font-mono text-indigo-300">python streaming/producer_test.py --rate 10 --duration 60</code>
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}
export default AnalyticsPage;
