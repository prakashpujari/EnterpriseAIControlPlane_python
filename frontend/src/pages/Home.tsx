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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Button,
  Chip,
} from '@mui/material';
import { RefreshCw, History } from 'lucide-react';
import { ChatWindow } from '../components/ChatWindow/ChatWindow';
import { RoleSelector, UserRole } from '../components/RoleSelector/RoleSelector';
import { MetricsPanel } from '../components/MetricsPanel/MetricsPanel';
import { useChat } from '../hooks/useChat';
import { useAuth } from '../store/authStore';
import { ExpandMore, HelpOutline } from '@mui/icons-material';

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

  // Helper to dispatch sample query event
  const dispatchSampleQuery = (query: string) => {
    window.dispatchEvent(new CustomEvent('sample-query', { detail: query }));
  };

  return (
    <Container maxWidth="lg" sx={{ py: 3, height: '100%' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h4" component="h1">
            Enterprise AI Customer Support
          </Typography>
          <Tooltip title="Help & Sample Queries">
            <IconButton onClick={() => alert('Sample Queries:\\n• FAQ: "What is your return policy?"\\n• Summarize: "Summarize the latest product manual"\\n• Reasoning: "How should I handle a frustrated customer requesting a refund outside the warranty period?"')}>
              <HelpOutline fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>

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

        {/* FAQ & Samples Panel */}
        <Grid item xs={12} md={4}>
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Metrics Panel (top) */}
            <Box sx={{ flex: 1, mb: 2 }}>
              <MetricsPanel role={role} />
            </Box>

            {/* Sample Queries & FAQs (bottom) */}
            <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
              <Typography variant="h5" component="h3" gutterBottom>
                Sample Queries
              </Typography>

              {/* FAQ Samples */}
              <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                Frequently Asked Questions
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('What is your return policy?')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  What is your return policy?
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('How do I reset my password?')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  How do I reset my password?
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('What are your business hours?')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  What are your business hours?
                </Button>
              </Box>

              {/* Summarization Samples */}
              <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                Summarization Tasks
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('Summarize the product warranty terms')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  Summarize warranty terms
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('Give me a brief summary of the user manual')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  Summarize user manual
                </Button>
              </Box>

              {/* Reasoning Samples */}
              <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                Complex Reasoning
              </Typography>
              <Box>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('How should I handle an angry customer who wants a refund after the warranty period?')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  Angry refund request
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('A customer received a damaged product and wants a replacement, but we are out of stock. What should I do?')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  Damaged item, out of stock
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => dispatchSampleQuery('Explain the escalation process for a security breach complaint')}
                  sx={{ mb: 1, width: '100%' }}
                >
                  Security breach escalation
                </Button>
              </Box>

              {/* FAQ Accordion */}
              <Typography variant="h5" component="h3" gutterBottom mt={4}>
                Frequently Asked Topics
              </Typography>
              <Accordion defaultExpanded>
                <AccordionSummary
                  expandIcon={<ExpandMore />}
                  aria-controls="panel1a-content"
                  id="panel1a-header"
                >
                  <Typography>What is your return policy?</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography>
                    Our standard return policy allows returns within 30 days of purchase with original receipt. Items must be in unused condition with original packaging. Certain items like software and consumables are non-returnable.
                  </Typography>
                </AccordionDetails>
              </Accordion>

              <Accordion defaultExpanded>
                <AccordionSummary
                  expandIcon={<ExpandMore />}
                  aria-controls="panel2a-content"
                  id="panel2a-header"
                >
                  <Typography>How do I reset my password?</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography>
                    To reset your password, click the 'Forgot Password' link on the login page, enter your email address, and follow the instructions sent to your inbox. If you don't receive the email, check your spam folder or contact support.
                  </Typography>
                </AccordionDetails>
              </Accordion>
            </Box>
          </Box>
        </Grid>
      </Grid>
    </Container>
  );
}