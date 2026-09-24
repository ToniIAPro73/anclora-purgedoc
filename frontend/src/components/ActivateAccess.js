import React, { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams, Navigate } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, ShieldCheck, CheckCircle2, AlertCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useApp } from "../context/AppContext";
import { api } from "../lib/api";
import { BrandMark } from "./BrandMark";
import LangToggle from "./LangToggle";
import ThemeToggle from "./ThemeToggle";

export default function ActivateAccess() {
  const [searchParams] = useSearchParams();
  const tokenParam = searchParams.get("token") || "";

  const { user, activate, loading } = useAuth();
  const { lang } = useApp();
  const en = lang === "en";
  const navigate = useNavigate();

  const [token, setToken] = useState(tokenParam);
  const [validating, setValidating] = useState(!!tokenParam);
  const [tokenValid, setTokenValid] = useState(false);
  const [validatedEmail, setValidatedEmail] = useState("");
  const [tokenError, setTokenError] = useState("");

  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Validate token with backend
  useEffect(() => {
    if (!tokenParam.trim()) {
      setValidating(false);
      return;
    }

    let isMounted = true;
    const validateToken = async () => {
      setValidating(true);
      setTokenError("");
      try {
        const res = await api.get(`/auth/activation/validate?token=${encodeURIComponent(tokenParam.trim())}`);
        if (isMounted) {
          if (res.data && res.data.valid) {
            setTokenValid(true);
            setValidatedEmail(res.data.email);
            setToken(tokenParam.trim());
          }
        }
      } catch (err) {
        if (isMounted) {
          setTokenValid(false);
          setTokenError(
            err.response?.data?.detail ||
              (en
                ? "Invalid, expired, or already used invitation token."
                : "Invitación no válida, expirada o ya utilizada.")
          );
        }
      } finally {
        if (isMounted) setValidating(false);
      }
    };

    validateToken();
    return () => {
      isMounted = false;
    };
  }, [tokenParam, en]);

  // If already authenticated, redirect to workspace
  if (!loading && user) {
    return <Navigate to="/app" replace />;
  }

  const handleManualTokenSubmit = async (e) => {
    e.preventDefault();
    if (!token.trim()) return;

    setValidating(true);
    setTokenError("");
    try {
      const res = await api.get(`/auth/activation/validate?token=${encodeURIComponent(token.trim())}`);
      if (res.data && res.data.valid) {
        setTokenValid(true);
        setValidatedEmail(res.data.email);
      }
    } catch (err) {
      setTokenValid(false);
      setTokenError(
        err.response?.data?.detail ||
          (en
            ? "Invalid, expired, or already used invitation token."
            : "Invitación no válida, expirada o ya utilizada.")
      );
    } finally {
      setValidating(false);
    }
  };

  const handleActivationSubmit = async (e) => {
    e.preventDefault();
    setFormError("");

    if (password.length < 12) {
      setFormError(
        en
          ? "Password must be at least 12 characters long."
          : "La contraseña debe tener al menos 12 caracteres."
      );
      return;
    }

    if (password !== confirmPassword) {
      setFormError(en ? "Passwords do not match." : "Las contraseñas no coinciden.");
      return;
    }

    setSubmitting(true);
    try {
      await activate(token, password, displayName.trim() || undefined);
      navigate("/app");
    } catch (err) {
      setFormError(
        err.response?.data?.detail ||
          (en ? "Error activating account. Please try again." : "Error al activar la cuenta. Inténtalo de nuevo.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      {/* Top Navigation */}
      <div className="auth-top">
        <Link to="/" className="auth-back">
          <ArrowLeft size={15} />
          <span>{en ? "Back to site" : "Volver al sitio"}</span>
        </Link>
        <div className="flex items-center gap-2">
          <LangToggle />
          <ThemeToggle />
        </div>
      </div>

      <div className="auth-glow auth-glow-one" />
      <div className="auth-glow auth-glow-two" />

      <section className="auth-card">
        <div className="auth-card-header">
          <BrandMark className="auth-logo rounded-full" />
          <div className="auth-divider" />
          <p className="tracking-tight text-base font-bold">
            Anclora <span className="text-[#38BDF8]">PurgeDoc</span>
          </p>
          <span className="text-xs text-slate-400 mt-1 block">
            {en ? "Account Activation" : "Activación de Cuenta"}
          </span>
        </div>

        {/* State 1: Validating token loading indicator */}
        {validating && (
          <div className="p-8 flex flex-col items-center justify-center gap-3">
            <div className="w-8 h-8 border-2 border-[#38BDF8] border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-slate-400">
              {en ? "Verifying invitation token..." : "Verificando token de invitación..."}
            </span>
          </div>
        )}

        {/* State 2: No valid token yet (manual input form) */}
        {!validating && !tokenValid && (
          <div className="auth-form">
            <p className="text-xs text-slate-300 mb-2">
              {en
                ? "Enter the access invitation token provided by your administrator:"
                : "Introduce el token de invitación proporcionado por tu administrador:"}
            </p>

            <form onSubmit={handleManualTokenSubmit} className="flex flex-col gap-3">
              <label htmlFor="token-input">{en ? "Invitation Token" : "Token de Invitación"}</label>
              <input
                id="token-input"
                data-testid="activation-token-input"
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="sec_..."
              />

              {tokenError && (
                <div role="alert" data-testid="activation-token-error" className="auth-error flex items-start gap-2">
                  <AlertCircle size={15} className="shrink-0 mt-0.5" />
                  <span>{tokenError}</span>
                </div>
              )}

              <button
                type="submit"
                data-testid="activation-token-submit"
                className="auth-submit cursor-pointer"
                disabled={!token.trim()}
              >
                {en ? "Validate Token" : "Validar Token"}
              </button>
            </form>

            <div className="mt-4 pt-3 border-t border-slate-700/50 text-center">
              <Link to="/login" className="text-xs text-[#38BDF8] hover:underline">
                {en ? "Already have an active account? Sign in" : "¿Ya tienes cuenta activa? Inicia sesión"}
              </Link>
            </div>
          </div>
        )}

        {/* State 3: Token is valid -> show activation form */}
        {!validating && tokenValid && (
          <form onSubmit={handleActivationSubmit} className="auth-form">
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-2.5 mb-2 flex items-center gap-2 text-xs text-emerald-400">
              <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
              <span>
                {en ? "Invitation verified for:" : "Invitación verificada para:"}{" "}
                <strong>{validatedEmail}</strong>
              </span>
            </div>

            {/* Read-only email */}
            <label htmlFor="act-email">{en ? "Email" : "Correo electrónico"}</label>
            <input
              id="act-email"
              data-testid="activation-email-readonly"
              type="email"
              readOnly
              value={validatedEmail}
              className="opacity-75 cursor-not-allowed bg-slate-900/80"
            />

            {/* Display Name */}
            <label htmlFor="act-name">{en ? "Full Name / Display Name" : "Nombre de usuario"}</label>
            <input
              id="act-name"
              data-testid="activation-name-input"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={en ? "Jane Doe" : "Nombre y apellidos"}
              disabled={submitting}
            />

            {/* Password */}
            <label htmlFor="act-password">
              {en ? "New Password" : "Nueva Contraseña"}
              <span className="text-[10px] text-slate-400 ml-1.5 font-normal">
                ({en ? "min. 12 characters" : "mínimo 12 caracteres"})
              </span>
            </label>
            <div className="auth-password">
              <input
                id="act-password"
                data-testid="activation-password-input"
                type={showPassword ? "text" : "password"}
                required
                minLength={12}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
              />
              <button
                type="button"
                data-testid="activation-password-toggle"
                aria-label={showPassword ? "Hide" : "Show"}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Confirm Password */}
            <label htmlFor="act-confirm-password">{en ? "Confirm Password" : "Confirmar Contraseña"}</label>
            <input
              id="act-confirm-password"
              data-testid="activation-confirm-password-input"
              type={showPassword ? "text" : "password"}
              required
              minLength={12}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={submitting}
            />

            {/* Password length indicator */}
            <div className="flex items-center gap-1.5 text-[11px] mt-1">
              <span className={password.length >= 12 ? "text-emerald-400" : "text-slate-400"}>
                {password.length >= 12 ? "✓" : "○"}{" "}
                {en ? "At least 12 characters" : "Al menos 12 caracteres"}
              </span>
              {password && confirmPassword && (
                <span className={`ml-auto ${password === confirmPassword ? "text-emerald-400" : "text-amber-400"}`}>
                  {password === confirmPassword
                    ? en
                      ? "✓ Passwords match"
                      : "✓ Coinciden"
                    : en
                    ? "✗ Do not match"
                    : "✗ No coinciden"}
                </span>
              )}
            </div>

            {formError && (
              <div role="alert" data-testid="activation-form-error" className="auth-error mt-2">
                {formError}
              </div>
            )}

            <button
              type="submit"
              data-testid="activation-submit-button"
              className="auth-submit cursor-pointer mt-3"
              disabled={submitting || password.length < 12 || password !== confirmPassword}
            >
              {submitting
                ? en
                  ? "Activating account..."
                  : "Activando cuenta..."
                : en
                ? "Activate Account & Enter"
                : "Activar Cuenta y Entrar"}
            </button>

            <div className="mt-3 pt-3 border-t border-slate-700/50 flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
              <ShieldCheck size={13} className="text-[#38BDF8]" />
              <span>{en ? "Single-use activation token" : "Token de activación de un solo uso"}</span>
            </div>
          </form>
        )}
      </section>
    </main>
  );
}
