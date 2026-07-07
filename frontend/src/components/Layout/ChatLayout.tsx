/**
 * ChatLayout Component
 * Main layout with sidebar, main chat area, and metrics panel
 */

import { Box, Container, Paper, Stack, Typography } from '@mui/material';
import { useState } from 'react';
import { ChatWindow } from '../ChatWindow/ChatWindow';
import { RoleSelector, UserRole } from '../RoleSelector/RoleSelector';
import { MetricsPanel } from '../MetricsPanel/MetricsPanel';

export function ChatLayout() {
  const [role, setRole] = useState<UserRole>('support_engineer');
  const [sessionId, setSessionId] = useState<string>('');

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h5">Enterprise AI Customer Support</Typography>
      </Box>

      {/* Main Content */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left Sidebar - Metrics */}
        <Paper
          elevation={2}
          sx={{
            width: 320,
            flexShrink: 0,
            p: 2,
            overflow: 'auto',
          }}
        >
          <Typography variant="h6" gutterBottom>
            Metrics
          </Typography>
          <MetricsPanel role={role} />
        </Paper>

        {/* Main Chat Area */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
            <RoleSelector
              selectedRole={role}
              onRoleChange={setRole}
            />
          </Box>
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            <ChatWindow role={role} sessionId={sessionId} />
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
