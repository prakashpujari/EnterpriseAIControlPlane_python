/**
 * MessageBubble Component
 * Displays individual chat messages with role-based styling
 */

import { Box, Typography, Paper, Chip, Avatar, Stack } from '@mui/material';
import { Bot, User, Cpu } from 'lucide-react';

interface MessageBubbleProps {
  message: {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    sources?: Array<{ title: string; source: string }>;
    timestamp: Date;
    model_used?: string;
  };
  role: string;
}

export function MessageBubble({ message, role }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
      }}
    >
      <Stack
        direction="row"
        spacing={1}
        alignItems="flex-start"
        sx={{
          maxWidth: '70%',
        }}
      >
        {/* Avatar */}
        <Avatar
          sx={{
            width: 32,
            height: 32,
            bgcolor: isUser ? 'primary.main' : 'secondary.main',
          }}
        >
          {isUser ? <User size={18} /> : <Bot size={18} />}
        </Avatar>

        {/* Message Bubble */}
        <Paper
          elevation={0}
          sx={{
            p: 1.5,
            borderRadius: 2,
            backgroundColor: isUser ? 'primary.light' : 'background.paper',
            border: 1,
            borderColor: isUser ? 'primary.main' : 'divider',
            width: '100%',
          }}
        >
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {message.content}
          </Typography>

          {/* Sources/Citations */}
          {message.sources && message.sources.length > 0 && (
            <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" component="div">
                Sources:
              </Typography>
              {message.sources.map((source, idx) => (
                <Chip
                  key={idx}
                  label={source.title}
                  size="small"
                  variant="outlined"
                  sx={{ mr: 0.5, mt: 0.5 }}
                />
              ))}
            </Box>
          )}

          {/* Model used indicator */}
          {isAssistant && message.model_used && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Cpu size={12} color="text.secondary" />
              <Typography variant="caption" color="text.secondary">
                Model: {message.model_used}
              </Typography>
            </Box>
          )}
        </Paper>
      </Stack>

      {/* Timestamp */}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ mt: 0.5 }}
      >
        {message.timestamp.toLocaleTimeString()}
      </Typography>
    </Box>
  );
}
