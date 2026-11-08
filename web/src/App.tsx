import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { useAuth } from './auth/context'
import { Spinner } from './components/Spinner'
import { AppShell } from './layout/AppShell'
import { LandingPage } from './pages/LandingPage'
import { NotFoundPage } from './pages/NotFoundPage'

// ── Lazy-loaded screens (one chunk per route entry) ──
const AccountPage = lazy(() => import('./pages/AccountPage').then((m) => ({ default: m.AccountPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const InstitutionAdminPage = lazy(() => import('./pages/institution/InstitutionAdminPage').then((m) => ({ default: m.InstitutionAdminPage })))
const PlatformAdminPage = lazy(() => import('./pages/admin/PlatformAdminPage').then((m) => ({ default: m.PlatformAdminPage })))
const SupplierWorkspacePage = lazy(() => import('./pages/supplier/SupplierWorkspacePage').then((m) => ({ default: m.SupplierWorkspacePage })))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const MfaPage = lazy(() => import('./pages/MfaPage').then((m) => ({ default: m.MfaPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage').then((m) => ({ default: m.VerifyEmailPage })))
const LogbookListPage = lazy(() => import('./pages/logbook/LogbookListPage').then((m) => ({ default: m.LogbookListPage })))
const ProcedureCreatePage = lazy(() => import('./pages/logbook/ProcedureCreatePage').then((m) => ({ default: m.ProcedureCreatePage })))
const ProcedureDetailPage = lazy(() => import('./pages/logbook/ProcedureDetailPage').then((m) => ({ default: m.ProcedureDetailPage })))
const ReportsPage = lazy(() => import('./pages/reports/ReportsPage').then((m) => ({ default: m.ReportsPage })))
const CatalogPage = lazy(() => import('./pages/marketplace/CatalogPage').then((m) => ({ default: m.CatalogPage })))
const ProductDetailPage = lazy(() => import('./pages/marketplace/ProductDetailPage').then((m) => ({ default: m.ProductDetailPage })))
const SubscriptionPage = lazy(() => import('./pages/marketplace/SubscriptionPage').then((m) => ({ default: m.SubscriptionPage })))
const CartPage = lazy(() => import('./pages/marketplace/CartPage').then((m) => ({ default: m.CartPage })))
const OrdersPage = lazy(() => import('./pages/marketplace/OrdersPage').then((m) => ({ default: m.OrdersPage })))
const OrderDetailPage = lazy(() => import('./pages/marketplace/OrderDetailPage').then((m) => ({ default: m.OrderDetailPage })))
const NotificationCenter = lazy(() => import('./pages/NotificationCenter').then((m) => ({ default: m.NotificationCenter })))
const PlacementListPage = lazy(() => import('./pages/training/PlacementListPage').then((m) => ({ default: m.PlacementListPage })))
const PlacementCreatePage = lazy(() => import('./pages/training/PlacementCreatePage').then((m) => ({ default: m.PlacementCreatePage })))
const PlacementDetailPage = lazy(() => import('./pages/training/PlacementDetailPage').then((m) => ({ default: m.PlacementDetailPage })))
const CompetencyCatalogPage = lazy(() => import('./pages/training/CompetencyCatalogPage').then((m) => ({ default: m.CompetencyCatalogPage })))
const CompetencyDetailPage = lazy(() => import('./pages/training/CompetencyDetailPage').then((m) => ({ default: m.CompetencyDetailPage })))
const AssessmentListPage = lazy(() => import('./pages/training/AssessmentListPage').then((m) => ({ default: m.AssessmentListPage })))
const AssessmentCreatePage = lazy(() => import('./pages/training/AssessmentCreatePage').then((m) => ({ default: m.AssessmentCreatePage })))
const AssessmentDetailPage = lazy(() => import('./pages/training/AssessmentDetailPage').then((m) => ({ default: m.AssessmentDetailPage })))
const PolicyCenterPage = lazy(() => import('./pages/legal/PolicyCenterPage').then((m) => ({ default: m.PolicyCenterPage })))
const PolicyDetailPage = lazy(() => import('./pages/legal/PolicyDetailPage').then((m) => ({ default: m.PolicyDetailPage })))
const PolicyHistoryPage = lazy(() => import('./pages/legal/PolicyHistoryPage').then((m) => ({ default: m.PolicyHistoryPage })))
const ConsentsPage = lazy(() => import('./pages/account/ConsentsPage').then((m) => ({ default: m.ConsentsPage })))
const LegalAdminPage = lazy(() => import('./pages/admin/LegalAdminPage').then((m) => ({ default: m.LegalAdminPage })))

function SessionLoading({ message }: { message: string }) {
  return (
    <div className="page-loading" role="status">
      <Spinner size="md" />
      <span>{message}</span>
    </div>
  )
}

function RedirectIfAuthenticated({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <SessionLoading message="Checking your session…" />
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
    return <SessionLoading message="Checking your session…" />
  }
  if (status === 'authenticated') {
    return <Navigate to="/dashboard" replace />
  }
  return <LandingPage />
}

function ScreenFallback() {
  return (
    <div className="page-loading" role="status">
      <Spinner size="md" />
      <span>Loading…</span>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<ScreenFallback />}>
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
        <Route path="/legal" element={<PolicyCenterPage />} />
        <Route path="/legal/policies/:slug/history" element={<PolicyHistoryPage />} />
        <Route path="/legal/policies/:slug" element={<PolicyDetailPage />} />
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
          <Route path="/marketplace/subscription" element={<SubscriptionPage />} />
          <Route path="/marketplace/products/:id" element={<ProductDetailPage />} />
          <Route path="/marketplace/cart" element={<CartPage />} />
          <Route path="/marketplace/orders" element={<OrdersPage />} />
          <Route path="/marketplace/orders/:id" element={<OrderDetailPage />} />
          <Route path="/account/consents" element={<ConsentsPage />} />
          <Route
            path="/admin/legal"
            element={
              <ProtectedRoute roles={['platform_admin']}>
                <LegalAdminPage />
              </ProtectedRoute>
            }
          />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}
