/**
 * ChatWindow Component
 * Displays conversation messages and input area
 */

import { useState, useRef, useEffect, FormEvent } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Paper,
  Typography,
  Divider,
  Avatar,
  Chip,
  Stack,
} from '@mui/material';
import { Send, Paperclip, Mic, Smile } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: Array<{ title: string; source: string }>;
  timestamp: Date;
  model_used?: string;
}

interface ChatWindowProps {
  role: string;
  sessionId: string;
}

export function ChatWindow({ role, sessionId }: ChatWindowProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    messages,
    isLoading,
    sendMessage,
    error,
  } = useChat(role, sessionId);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Listen for sample query events from Home page
  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      if (customEvent.type === 'sample-query') {
        setInputValue(customEvent.detail);
        // Focus input after setting value
        inputRef.current?.focus();
      }
    };
    window.addEventListener('sample-query', handler);
    return () => {
      window.removeEventListener('sample-query', handler);
    };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    await sendMessage(inputValue);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === '\n' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Messages Area */}
      <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
        {messages.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="h6" color="text.secondary">
              Welcome to Enterprise AI Customer Support
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              How can I help you today?
            </Typography>
          </Box>
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              role={role}
            />
          ))
        )}

        {isLoading && <TypingIndicator />}

        <Box ref={messagesEndRef} />

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Box>

      <Divider />

      {/* Input Area */}
      <Box component="form" onSubmit={handleSubmit} sx={{ p: 2 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <IconButton type="button" aria-label="attach file">
            <Paperclip />
          </IconButton>

          <TextField
            ref={inputRef}
            fullWidth
            multiline
            maxRows={6}
            minRows={2}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            onKeyDown={handleKeyDown}
            variant="outlined"
            size="small"
          />

          <IconButton type="button" aria-label="voice input">
            <Mic />
          </IconButton>

          <IconButton type="button" aria-label="emoji">
            <Smile />
          </IconButton>

          <IconButton
            type="submit"
            aria-label="send"
            disabled={!inputValue.trim() || isLoading}
            color="primary"
            variant="contained"
          >
            <Send />
          </IconButton>
        </Stack>

        <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
          <Chip
            label="Press Enter to send"
            size="small"
            variant="outlined"
          />
          <Chip
            label="Shift + Enter for new line"
            size="small"
            variant="outlined"
          />
        </Box>
      </Box>
    </Box>
  );
}

/**
 * Alert component for error display
 */
interface AlertProps {
  severity: 'error' | 'warning' | 'info' | 'success';
  children: React.ReactNode;
}

function Alert({ severity, children }: AlertProps) {
  return (
    <Paper
      elevation={3}
      sx={{
        p: 2,
        borderRadius: 1,
        backgroundColor: `error.light`,
        color: 'error.contrastText',
      }}
    >
      {children}
    </Paper>
  );
}