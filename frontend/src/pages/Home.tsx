/**
 * Home Page Component
 * Main chat interface with role selector and metrics
 */

import { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
  Paper,
  Typography,
  IconButton,
  Tooltip,
} from '@mui/material';
import { RefreshCw, History } from 'lucide-react';
import { ChatWindow } from '../components/ChatWindow/ChatWindow';
import { RoleSelector, UserRole } from '../components/RoleSelector/RoleSelector';
import { MetricsPanel } from '../components/MetricsPanel/MetricsPanel';
import { useChat } from '../hooks/useChat';
import { useAuth } from '../store/authStore';

export function Home() {
  const [role, setRole] = useState<UserRole>('support_engineer');
  const [sessionId, setSessionId] = useState<string>('');
  const { user } = useAuth();

  // Generate or get session ID
  useEffect(() => {
    const storedSessionId = localStorage.getItem('current_session_id');
    if (storedSessionId) {
      setSessionId(storedSessionId);
    } else {
      const newSessionId = `session_${Date.now()}`;
      setSessionId(newSessionId);
      localStorage.setItem('current_session_id', newSessionId);
    }
  }, []);

  // Store role in localStorage
  useEffect(() => {
    localStorage.setItem('user_role', role);
  }, [role]);

  return (
    <Container maxWidth="lg" sx={{ py: 3, height: '100%' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h4" component="h1">
          Enterprise AI Customer Support
        </Typography>

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Tooltip title="Refresh">
            <IconButton>
              <RefreshCw />
            </IconButton>
          </Tooltip>

          <Tooltip title="View History">
            <IconButton>
              <History />
            </IconButton>
          </Tooltip>

          <Typography variant="body2" color="text.secondary">
            {user?.email || 'User'}
          </Typography>
        </Box>
      </Box>

      {/* Role Selector */}
      <RoleSelector
        selectedRole={role}
        onRoleChange={setRole}
      />

      {/* Main Content */}
      <Grid container spacing={2} sx={{ height: 'calc(100vh - 200px)' }}>
        {/* Chat Area */}
        <Grid item xs={12} md={8}>
          <Paper
            elevation={3}
            sx={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <ChatWindow role={role} sessionId={sessionId} />
          </Paper>
        </Grid>

        {/* Metrics Panel */}
        <Grid item xs={12} md={4}>
          <MetricsPanel role={role} />
        </Grid>
      </Grid>
    </Container>
  );
}
