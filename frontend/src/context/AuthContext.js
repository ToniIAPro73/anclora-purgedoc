import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkSession = useCallback(async () => {
    try {
      const res = await api.get("/auth/me");
      if (res.data && res.data.authenticated) {
        setUser(res.data.user);
      } else {
        setUser(null);
      }
    } catch (err) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const login = async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    if (res.data) {
      setUser(res.data);
      return res.data;
    }
  };

  const activate = async (token, password, displayName) => {
    const res = await api.post("/auth/activate", {
      token,
      password,
      display_name: displayName,
    });
    if (res.data) {
      setUser(res.data);
      return res.data;
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout", {});
    } catch (e) {
      // ignore network errors on logout
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, login, activate, logout, checkSession }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

export default AuthContext;
