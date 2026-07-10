/**
 * Settings Page Component
 * User preferences and configuration
 */

import { useState, useEffect } from 'react';
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
  CircularProgress,
  Alert,
} from '@mui/material';
import { useAuth } from '../store/authStore';
import axios from 'axios';

export function Settings() {
  const [settings, setSettings] = useState({
    notifications: true,
    darkMode: false,
    apiAccess: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { user } = useAuth();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/api/v1/settings/`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });
      setSettings({
        notifications: response.data.notification_preference,
        darkMode: response.data.dark_mode,
        apiAccess: response.data.api_access,
      });
    } catch (err: any) {
      setError('Failed to load settings');
      console.error('Error loading settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      await axios.put(
        `${import.meta.env.VITE_API_URL}/api/v1/settings/`,
        {
          notification_preference: settings.notifications,
          dark_mode: settings.darkMode,
          api_access: settings.apiAccess,
        },
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );
      setSuccess('Settings saved successfully!');
    } catch (err: any) {
      setError('Failed to save settings');
      console.error('Error saving settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);
      await axios.post(
        `${import.meta.env.VITE_API_URL}/api/v1/settings/reset`,
        {},
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );
      setSettings({
        notifications: true,
        darkMode: false,
        apiAccess: false,
      });
      setSuccess('Settings reset to defaults!');
    } catch (err: any) {
      setError('Failed to reset settings');
      console.error('Error resetting settings:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}
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
                disabled={loading}
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
                  disabled={loading}
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
                  disabled={loading}
                />
              }
              label="Enable API Access"
            />
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
          {loading && <CircularProgress size={24} />}
          <Button variant="outlined" onClick={handleReset} disabled={loading}>
            Reset to Defaults
          </Button>
          <Button variant="outlined" onClick={() => {/* Cancel - just reset form */}} disabled={loading}>
            Cancel
          </Button>
          <Button variant="contained" onClick={handleSave} disabled={loading}>
            Save Settings
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}