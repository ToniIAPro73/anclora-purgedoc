import React from 'react';
import ReactDOMServer from 'react-dom/server';
import Landing from './components/Landing';
import Login from './components/Login';
import ActivateAccess from './components/ActivateAccess';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './context/AuthContext';
import { AppProvider } from './context/AppContext';

// Mock react-router-dom components and hooks for deterministic Jest SSR testing
jest.mock('react-router-dom', () => ({
  Link: ({ to, children, className, ...props }) => (
    <a href={to} className={className} {...props}>
      {children}
    </a>
  ),
  Navigate: ({ to }) => <div data-testid="navigate-redirect" data-to={to} />,
  useNavigate: () => () => {},
  useSearchParams: () => [new URLSearchParams(), () => {}],
  BrowserRouter: ({ children }) => <div>{children}</div>,
  MemoryRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: ({ element }) => element,
}));

describe('PurgeDoc Frontend Public Surfaces & Auth Access Control', () => {
  test('Landing renders unauthenticated public surface with PurgeDoc brand and capabilities', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <AppProvider>
          <Landing />
        </AppProvider>
      </AuthProvider>
    );

    expect(html).toBeDefined();
    expect(html).toContain('PurgeDoc');
    expect(html).toContain('anclora-purgedoc');
    // Must contain Sign in or Iniciar sesión
    expect(html).toMatch(/Iniciar sesión|Sign in/);
    // Must contain Activate access CTA
    expect(html).toMatch(/Activar acceso|Activate access/);
    // Must communicate physical redaction / fail-closed
    expect(html).toMatch(/FAIL-CLOSED|Purga Física|verificación|redacción física/i);
    // MUST NOT contain free public registration
    expect(html).not.toContain('Crear cuenta gratis');
    expect(html).not.toContain('Sign up for free');
  });

  test('Login page renders email/password form with visible but disabled social buttons', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <AppProvider>
          <Login />
        </AppProvider>
      </AuthProvider>
    );

    expect(html).toBeDefined();
    expect(html).toContain('data-testid="login-email-input"');
    expect(html).toContain('data-testid="login-password-input"');
    expect(html).toContain('data-testid="login-submit-button"');
    expect(html).toContain('data-testid="login-password-toggle"');
    // Link to activation
    expect(html).toMatch(/Activar acceso|Activate access/);

    // Social login buttons are VISIBLE but strictly DISABLED
    expect(html).toContain('data-testid="social-google-disabled"');
    expect(html).toContain('data-testid="social-github-disabled"');
    expect(html).toContain('disabled=""');
    expect(html).toContain('aria-disabled="true"');
    expect(html).toMatch(/Próx|Soon/);

    // STRICT: No OAuth routes, no client IDs, no free public registration
    expect(html).not.toContain('/api/auth/google');
    expect(html).not.toContain('/api/auth/github');
    expect(html).not.toContain('Crear cuenta gratis');
    expect(html).not.toContain('Sign up for free');
  });

  test('ActivateAccess renders invitation token validation interface', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <AppProvider>
          <ActivateAccess />
        </AppProvider>
      </AuthProvider>
    );

    expect(html).toBeDefined();
    expect(html).toContain('data-testid="activation-token-input"');
    expect(html).toContain('data-testid="activation-token-submit"');
    expect(html).toMatch(/Token de Invitación|Invitation Token/);
  });

  test('ProtectedRoute blocks unauthenticated access without rendering children', () => {
    const html = ReactDOMServer.renderToString(
      <AuthProvider>
        <ProtectedRoute>
          <div data-testid="secret-workspace">Sensitive PurgeDoc Document Data</div>
        </ProtectedRoute>
      </AuthProvider>
    );

    // Initial unauth state must not leak sensitive workspace content
    expect(html).not.toContain('Sensitive PurgeDoc Document Data');
  });

  test('No free registration exists across any public view', () => {
    const views = [
      <AuthProvider><AppProvider><Landing /></AppProvider></AuthProvider>,
      <AuthProvider><AppProvider><Login /></AppProvider></AuthProvider>,
      <AuthProvider><AppProvider><ActivateAccess /></AppProvider></AuthProvider>
    ];

    views.forEach((view) => {
      const html = ReactDOMServer.renderToString(view);
      expect(html).not.toContain('oauth_identities');
      expect(html).not.toContain('free-registration');
      expect(html).not.toContain('Crear cuenta gratis');
      expect(html).not.toContain('Register for free');
    });
  });
});
