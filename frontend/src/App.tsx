import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { homePath } from './auth/session'
import { RequireAuth } from './auth/RequireAuth'
import { RequireRole } from './auth/RequireRole'
import { useAuth } from './auth/useAuth'
import { AppShell } from './layouts/AppShell'
import { LoginPage } from './pages/LoginPage'
import { MyDossiersPage } from './pages/MyDossiersPage'
import { OverviewPage } from './pages/OverviewPage'
import { AnalysisProgressPage } from './pages/AnalysisProgressPage'
import { CreateDossierPage } from './pages/CreateDossierPage'
import { DossierReviewPage } from './pages/DossierReviewPage'
import { CitationComparePage } from './pages/CitationComparePage'
import { CitationSplitViewPage } from './pages/CitationSplitViewPage'
import { CitationEditPage } from './pages/CitationEditPage'
import { ClauseConflictPage } from './pages/ClauseConflictPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { ReviewLayout } from './layouts/ReviewLayout'

function AuthRedirect() {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/" replace />
  }
  return <Navigate to={homePath(user.role)} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<AppShell />}>
              <Route
                path="/tong-quan"
                element={
                  <RequireRole allow="admin">
                    <OverviewPage />
                  </RequireRole>
                }
              />
              <Route
                path="/nguoi-dung-phan-quyen"
                element={
                  <RequireRole allow="admin">
                    <PlaceholderPage title="Người dùng & Phân quyền" />
                  </RequireRole>
                }
              />
              <Route
                path="/ho-so"
                element={
                  <RequireRole allow="admin">
                    <MyDossiersPage />
                  </RequireRole>
                }
              />
              <Route
                path="/nhat-ky-hoat-dong"
                element={
                  <RequireRole allow="admin">
                    <PlaceholderPage title="Nhật ký hoạt động" />
                  </RequireRole>
                }
              />
              <Route
                path="/ho-so-cua-toi"
                element={
                  <RequireRole allow="user">
                    <MyDossiersPage />
                  </RequireRole>
                }
              />
              <Route
                path="/duoc-chia-se-voi-toi"
                element={
                  <RequireRole allow="user">
                    <PlaceholderPage title="Được chia sẻ với tôi" />
                  </RequireRole>
                }
              />
              <Route
                path="/tim-kiem-xuyen-ho-so"
                element={
                  <RequireRole allow="user">
                    <PlaceholderPage title="Tìm kiếm xuyên hồ sơ" />
                  </RequireRole>
                }
              />
              <Route
                path="/doi-soat-xung-dot"
                element={<ClauseConflictPage />}
              />
              <Route path="/tao-ho-so" element={<CreateDossierPage />} />
              <Route
                path="/tien-trinh-phan-tich"
                element={<AnalysisProgressPage />}
              />
              <Route
                path="/cai-dat"
                element={<PlaceholderPage title="Cài đặt" />}
              />
            </Route>
            <Route element={<ReviewLayout />}>
              <Route path="/ho-so-hop-dong" element={<DossierReviewPage />} />
              <Route
                path="/doi-soat-trich-dan"
                element={<CitationComparePage />}
              />
              <Route
                path="/nhan-xet-chinh-sua"
                element={<CitationSplitViewPage />}
              />
              <Route
                path="/chinh-sua-trich-dan"
                element={<CitationEditPage />}
              />
              <Route
                path="/trung-tam-phan-tich"
                element={<PlaceholderPage title="Trung tâm Phân tích" />}
              />
              <Route
                path="/kho-dieu-khoan-mau"
                element={<PlaceholderPage title="Kho Điều khoản Mẫu" />}
              />
              <Route
                path="/tuan-thu-rui-ro"
                element={<PlaceholderPage title="Tuân thủ & Rủi ro" />}
              />
              <Route path="/nhat-ky-phap-ly" element={<DossierReviewPage />} />
            </Route>
          </Route>
          <Route path="*" element={<AuthRedirect />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
