import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { LoginPage } from "./pages/LoginPage";
import { ChatPage } from "./pages/ChatPage";
import { useAuthStore } from "./store/authStore";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useWebSocket } from "./hooks/useWebSocket";

import { AnalyticsPage } from "./pages/AnalyticsPage";

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Wait for zustand-persist to rehydrate from localStorage before rendering routes.
  // This prevents the first API call from firing with a null token (→ 401) on page refresh.
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // zustand persist with localStorage rehydrates synchronously during store creation,
    // so by the time this effect runs the store is already populated.
    // We still defer one tick so the initial render always sees the persisted values.
    setHydrated(true);
  }, []);

  // Initialize WebSocket connection once globally
  useWebSocket();

  if (!hydrated) return null;

  return (
    <BrowserRouter>
      <Routes>
        <Route 
          path="/" 
          element={<Navigate to={isAuthenticated ? "/chat" : "/login"} replace />} 
        />
        <Route 
          path="/login" 
          element={isAuthenticated ? <Navigate to="/chat" replace /> : <LoginPage />} 
        />
        <Route 
          path="/chat" 
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/chat/:conversationId" 
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/analytics" 
          element={
            <ProtectedRoute>
              <AnalyticsPage />
            </ProtectedRoute>
          } 
        />
        {/* Fallback route */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
