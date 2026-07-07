/**
 * MetricsPanel Component
 * Displays token usage, cost, and drift indicators
 */

import {
  Box,
  Typography,
  Paper,
  Stack,
  Divider,
  LinearProgress,
  Tooltip,
} from '@mui/material';
import {
  Zap,
  CreditCard,
  TrendingDown,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';
import { useMetrics } from '../../hooks/useMetrics';

interface MetricsPanelProps {
  role: string;
}

export function MetricsPanel({ role }: MetricsPanelProps) {
  const { metrics, driftDetected, resetMetrics } = useMetrics();

  return (
    <Paper
      elevation={2}
      sx={{
        width: '100%',
        maxWidth: 320,
        height: '100%',
        p: 2,
      }}
    >
      <Typography variant="h6" gutterBottom>
        Metrics
      </Typography>

      <Stack spacing={2}>
        {/* Token Usage */}
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2" color="text.secondary">
              Tokens
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {metrics.tokens_input + metrics.tokens_output}
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={(metrics.tokens_input + metrics.tokens_output) / 8000 * 100}
            color={metrics.tokens_input + metrics.tokens_output > 6000 ? 'error' : 'primary'}
            sx={{ height: 6, borderRadius: 3 }}
          />
          <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              In: {metrics.tokens_input}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Out: {metrics.tokens_output}
            </Typography>
          </Box>
        </Box>

        <Divider />

        {/* Cost */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <CreditCard size={18} color="success" />
            <Typography variant="body2" color="text.secondary">
              Estimated Cost
            </Typography>
          </Box>
          <Typography variant="h6" color="success.main">
            ${metrics.cost.toFixed(4)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {role} token limit: 8000
          </Typography>
        </Box>

        <Divider />

        {/* Drift Indicators */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            {driftDetected ? (
              <AlertCircle size={18} color="error" />
            ) : (
              <CheckCircle size={18} color="success" />
            )}
            <Typography variant="body2" color="text.secondary">
              Quality Status
            </Typography>
          </Box>
          {driftDetected ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingDown size={16} color="error" />
              <Typography variant="caption" color="error.main">
                Drift detected - using fallback model
              </Typography>
            </Box>
          ) : (
            <Typography variant="caption" color="success.main">
              All systems nominal
            </Typography>
          )}
        </Box>

        <Divider />

        {/* Model Info */}
        <Box>
          <Typography variant="body2" color="text.secondary" mb={0.5}>
            Current Model
          </Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
            {metrics.model_used}
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
}
