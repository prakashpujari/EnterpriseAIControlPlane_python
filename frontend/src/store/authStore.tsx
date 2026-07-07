/**
 * Authentication Store
 * Manages user authentication state using React Context
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface User {
  id: string;
  email: string;
  role: string;
  full_name?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// When auth is disabled for local development (VITE_DISABLE_AUTH=true),
// treat the app as already signed in with a built-in dev identity so the
// chat UI is usable without a login flow.
const DISABLE_AUTH = import.meta.env.VITE_DISABLE_AUTH === 'true';
const DEV_USER: User = {
  id: 'dev-user',
  email: 'dev@example.com',
  role: 'support_engineer',
  full_name: 'Dev User',
};
const DEV_TOKEN = 'dev-token';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load token from localStorage on mount
  useEffect(() => {
    if (DISABLE_AUTH) {
      setToken(DEV_TOKEN);
      setUser(DEV_USER);
      setIsLoading(false);
      return;
    }

    const storedToken = localStorage.getItem('token');
    const storedUser = localStorage.getItem('user');

    if (storedToken && storedUser && storedUser !== 'undefined') {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch (e) {
        console.error('Failed to parse stored user:', e);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }

    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/auth/login`, {
        email,
        password,
      });

      const { access_token, user: userResponse } = response.data;

      setToken(access_token);
      setUser(userResponse);

      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(userResponse));
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }, []);

  const authValue: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={authValue}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}