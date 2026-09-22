import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI, getAuthToken, setAuthToken, getUserData, setUserData } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(getUserData());
  const [token, setToken] = useState(getAuthToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = getAuthToken();
      if (storedToken) {
        try {
          const profile = await authAPI.getMe();
          setUser(profile);
          setUserData(profile);
          setToken(storedToken);
        } catch {
          // Token expired or invalid
          setAuthToken(null);
          setUserData(null);
          setUser(null);
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (username, password) => {
    const response = await authAPI.login(username, password);
    setAuthToken(response.access_token);
    setUserData(response.user);
    setToken(response.access_token);
    setUser(response.user);
    return response.user;
  };

  const logout = () => {
    setAuthToken(null);
    setUserData(null);
    setUser(null);
    setToken(null);
  };

  const hasRole = (...roles) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        isAuthenticated: !!user && !!token,
        isSuperAdmin: user?.role === 'superadmin',
        isAdmin: user?.role === 'admin',
        isManager: user?.role === 'superadmin', // Legacy alias mapped to SuperAdmin
        isStaff: user?.role === 'staff',
        isCustomer: user?.role === 'customer',
        hasRole,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
