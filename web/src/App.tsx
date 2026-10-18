import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { useAuth } from './auth/context'
import { Spinner } from './components/Spinner'
import { AccountPage } from './pages/AccountPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { MfaPage } from './pages/MfaPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'
import { AppShell } from './layout/AppShell'

function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" />
        <span>Checking your session…</span>
      </div>
    )
  }
  if (status === 'authenticated') {
    const from = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={from} replace />
  }
  return children
}

function LandingRoute() {
  const { status } = useAuth()

  if (status === 'loading') {
    return (
      <div className="page-loading" role="status">
        <Spinner size="md" />
        <span>Checking your session…</span>
      </div>
    )
  }
  if (status === 'authenticated') {
    return <Navigate to="/account" replace />
  }
  return <LandingPage />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingRoute />} />
      <Route
        path="/login"
        element={
          <RedirectIfAuthenticated>
            <LoginPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthenticated>
            <RegisterPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/verify-email"
        element={
          <RedirectIfAuthenticated>
            <VerifyEmailPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/forgot-password"
        element={
          <RedirectIfAuthenticated>
            <ForgotPasswordPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/reset-password"
        element={
          <RedirectIfAuthenticated>
            <ResetPasswordPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        path="/mfa"
        element={
          <RedirectIfAuthenticated>
            <MfaPage />
          </RedirectIfAuthenticated>
        }
      />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/account" element={<AccountPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
