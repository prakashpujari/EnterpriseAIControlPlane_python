/**
 * Settings Page Component
 * User preferences and configuration
 */

import { useState } from 'react';
import {
  Box,
  Button,
  Container,
  Typography,
  Paper,
  TextField,
  Switch,
  FormControlLabel,
  Divider,
} from '@mui/material';
import { useAuth } from '../store/authStore';

export function Settings() {
  const [settings, setSettings] = useState({
    notifications: true,
    darkMode: false,
    apiAccess: false,
  });
  const { user } = useAuth();

  const handleSave = () => {
    // TODO: Save settings to backend
    console.log('Settings saved:', settings);
  };

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Settings
      </Typography>

      <Paper elevation={3} sx={{ p: 3 }}>
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            User Information
          </Typography>
          <TextField
            label="Email"
            value={user?.email || ''}
            InputProps={{ readOnly: true }}
            fullWidth
            sx={{ mb: 2 }}
          />
          <TextField
            label="Full Name"
            value={user?.full_name || ''}
            InputProps={{ readOnly: true }}
            fullWidth
          />
        </Box>

        <Divider sx={{ my: 2 }} />

        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Preferences
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={settings.notifications}
                onChange={(e) => setSettings({ ...settings, notifications: e.target.checked })}
              />
            }
            label="Enable Notifications"
          />

          <Box sx={{ mt: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.darkMode}
                  onChange={(e) => setSettings({ ...settings, darkMode: e.target.checked })}
                />
              }
              label="Dark Mode"
            />
          </Box>

          <Box sx={{ mt: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.apiAccess}
                  onChange={(e) => setSettings({ ...settings, apiAccess: e.target.checked })}
                />
              }
              label="Enable API Access"
            />
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
          <Button variant="outlined">Cancel</Button>
          <Button variant="contained" onClick={handleSave}>
            Save Settings
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}
