import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { useAuth } from './auth/context'
import { Spinner } from './components/Spinner'
import { AccountPage } from './pages/AccountPage'
import { DashboardPage } from './pages/DashboardPage'
import { InstitutionAdminPage } from './pages/institution/InstitutionAdminPage'
import { PlatformAdminPage } from './pages/admin/PlatformAdminPage'
import { SupplierWorkspacePage } from './pages/supplier/SupplierWorkspacePage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { MfaPage } from './pages/MfaPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'
import { AppShell } from './layout/AppShell'
import { LogbookListPage } from './pages/logbook/LogbookListPage'
import { ProcedureCreatePage } from './pages/logbook/ProcedureCreatePage'
import { ProcedureDetailPage } from './pages/logbook/ProcedureDetailPage'
import { ReportsPage } from './pages/reports/ReportsPage'
import { CatalogPage } from './pages/marketplace/CatalogPage'
import { ProductDetailPage } from './pages/marketplace/ProductDetailPage'
import { CartPage } from './pages/marketplace/CartPage'
import { OrdersPage } from './pages/marketplace/OrdersPage'
import { OrderDetailPage } from './pages/marketplace/OrderDetailPage'
import { NotificationCenter } from './pages/NotificationCenter'
import { PlacementListPage } from './pages/training/PlacementListPage'
import { PlacementCreatePage } from './pages/training/PlacementCreatePage'
import { PlacementDetailPage } from './pages/training/PlacementDetailPage'
import { CompetencyCatalogPage } from './pages/training/CompetencyCatalogPage'
import { CompetencyDetailPage } from './pages/training/CompetencyDetailPage'
import { AssessmentListPage } from './pages/training/AssessmentListPage'
import { AssessmentCreatePage } from './pages/training/AssessmentCreatePage'
import { AssessmentDetailPage } from './pages/training/AssessmentDetailPage'

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
    return <Navigate to="/dashboard" replace />
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
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/notifications" element={<NotificationCenter />} />
        <Route path="/training" element={<PlacementListPage />} />
        <Route path="/training/placements/new" element={<PlacementCreatePage />} />
        <Route path="/training/placements/:id" element={<PlacementDetailPage />} />
        <Route path="/training/competencies" element={<CompetencyCatalogPage />} />
        <Route path="/training/competencies/:id" element={<CompetencyDetailPage />} />
        <Route path="/training/assessments" element={<AssessmentListPage />} />
        <Route path="/training/assessments/new" element={<AssessmentCreatePage />} />
        <Route path="/training/assessments/:id" element={<AssessmentDetailPage />} />
        <Route path="/institution" element={<InstitutionAdminPage />} />
        <Route path="/supplier" element={<SupplierWorkspacePage />} />
        <Route path="/admin" element={<PlatformAdminPage />} />
        <Route path="/logbook" element={<LogbookListPage />} />
        <Route path="/logbook/new" element={<ProcedureCreatePage />} />
        <Route path="/logbook/:id" element={<ProcedureDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/marketplace" element={<CatalogPage />} />
        <Route path="/marketplace/products/:id" element={<ProductDetailPage />} />
        <Route path="/marketplace/cart" element={<CartPage />} />
        <Route path="/marketplace/orders" element={<OrdersPage />} />
        <Route path="/marketplace/orders/:id" element={<OrderDetailPage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
