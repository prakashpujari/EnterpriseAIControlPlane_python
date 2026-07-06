/**
 * useChat Hook
 * Manages chat state and API interactions
 */

import { useState, useCallback, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import axios, { AxiosError } from 'axios';
import { v4 as uuidv4 } from 'uuid';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: Array<{ title: string; source: string }>;
  timestamp: Date;
}

interface ChatResponse {
  response: string;
  session_id: string;
  sources: Array<{ title: string; source: string }>;
  model_used: string;
  tokens_input: number;
  tokens_output: number;
  latency_ms: number;
  is_valid: boolean;
  suggestions: string[];
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 60000,
});

// Request interceptor for auth
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function useChat(role: string, sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Load messages for session (would fetch from API in full implementation)
  useEffect(() => {
    // In production, fetch messages from API
    // For now, we'll manage locally
  }, [sessionId]);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      const userMessage: Message = {
        id: uuidv4(),
        role: 'user',
        content,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const response = await apiClient.post<ChatResponse>('/chat', {
          query: content,
          role,
          session_id: sessionId,
        });

        const assistantMessage: Message = {
          id: uuidv4(),
          role: 'assistant',
          content: response.data.response,
          sources: response.data.sources,
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMessage]);

        // Invalidate metrics query
        queryClient.invalidateQueries({ queryKey: ['metrics'] });

      } catch (err) {
        const errorMessage =
          err instanceof AxiosError
            ? err.response?.data?.message || err.message
            : 'Failed to send message';

        setError(errorMessage);
        console.error('Chat error:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [role, sessionId, isLoading, queryClient]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  };
}
