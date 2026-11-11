/**
 * Router definitions.
 * - Public routes: / (landing), /login, /change-password
 * - Protected routes: everything else, inside AppShell.
 * - 404 fallback.
 */
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { ChangePassword } from "./pages/ChangePassword";
import { Dashboard } from "./pages/Dashboard";
import { PlanningCycles } from "./pages/PlanningCycles";
import { PlanningCycleDetail } from "./pages/PlanningCycleDetail";
import { Resources } from "./pages/Resources";
import { Offerings, OfferingDetail } from "./pages/Offerings";
import { OfferingResourceSelection } from "./pages/OfferingResourceSelection";
import { Submissions, SubmissionWizard } from "./pages/Submissions";
import { SharedOfferingsPage } from "./pages/SharedOfferings";
import { PreflightPage } from "./pages/Preflight";
import { SolverPage } from "./pages/Solver";
import { Runs, RunDetailPage } from "./pages/Runs";
import { Audit } from "./pages/Audit";
import { CycleEditPage } from "./pages/CycleEditPage";

function RequireAuth({ children }: { children: JSX.Element }) {
  const auth = useAuth();
  if (!auth.accessToken) return <Navigate to="/login" replace />;
  if (auth.mustChangePassword) return <Navigate to="/change-password" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />

      <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/cycles" element={<RequireAuth><PlanningCycles /></RequireAuth>} />
      <Route path="/cycles/:cycleId" element={<RequireAuth><PlanningCycleDetail /></RequireAuth>} />
      <Route path="/cycles/:cycleId/edit" element={<RequireAuth><CycleEditPage /></RequireAuth>} />
      <Route path="/resources" element={<RequireAuth><Resources /></RequireAuth>} />
      <Route path="/offerings" element={<RequireAuth><Offerings /></RequireAuth>} />
      <Route path="/offerings/:offeringId" element={<RequireAuth><OfferingDetail /></RequireAuth>} />
      <Route path="/offerings/:offeringId/units/:unitId/resources" element={<RequireAuth><OfferingResourceSelection /></RequireAuth>} />
      <Route path="/submissions" element={<RequireAuth><Submissions /></RequireAuth>} />
      <Route path="/submissions/:submissionId" element={<RequireAuth><SubmissionWizard /></RequireAuth>} />
      <Route path="/shared" element={<RequireAuth><SharedOfferingsPage /></RequireAuth>} />
      <Route path="/preflight" element={<RequireAuth><PreflightPage /></RequireAuth>} />
      <Route path="/solve" element={<RequireAuth><SolverPage /></RequireAuth>} />
      <Route path="/runs" element={<RequireAuth><Runs /></RequireAuth>} />
      <Route path="/runs/:runId" element={<RequireAuth><RunDetailPage /></RequireAuth>} />
      <Route path="/audit" element={<RequireAuth><Audit /></RequireAuth>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

