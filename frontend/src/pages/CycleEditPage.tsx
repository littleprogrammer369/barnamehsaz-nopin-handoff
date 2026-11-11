/**
 * Cycle edit and archive page.
 * Admin-only: edit cycle details, archive cycle.
 */
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Cycles } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import { Card, Loading, ErrorState, Alert } from "../components/ui";

export function CycleEditPage() {
  const { cycleId } = useParams();
  const navigate = useNavigate();
  const id = Number(cycleId);

  const cycleQ = useQuery(() => Cycles.get(id), [id]);
  
  const [name, setName] = useState("");
  const [term, setTerm] = useState("");
  const [startDate, setStartDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Initialize form when cycle loads
  if (cycleQ.data && !name) {
    setName(cycleQ.data.name);
    setTerm(cycleQ.data.term || "");
    setStartDate(cycleQ.data.start_date?.split("T")[0] || "");
  }

  if (cycleQ.loading) {
    return <AppShell title="ویرایش چرخه"><Loading /></AppShell>;
  }

  if (cycleQ.error || !cycleQ.data) {
    return <AppShell title="ویرایش چرخه"><ErrorState message={cycleQ.error ?? "چرخه یافت نشد"} onRetry={cycleQ.reload} /></AppShell>;
  }

  const handleUpdate = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);
    
    try {
      const response = await fetch(`/api/v1/phase2/cycles/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          name,
          term: term || null,
          start_date: startDate ? new Date(startDate).toISOString() : null,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || `HTTP ${response.status}`);
      }

      setSuccess(true);
      setTimeout(() => navigate(`/cycles/${id}`), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    } finally {
      setLoading(false);
    }
  };

  const handleArchive = async () => {
    if (!confirm("آیا مطمئن هستید که می‌خواهید این چرخه را بایگانی کنید؟")) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/v1/phase2/cycles/${id}/archive`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || `HTTP ${response.status}`);
      }

      navigate("/cycles");
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell title={`ویرایش چرخه: ${name}`}>
      <div className="mt-2">
        {error && <Alert kind="bad">{error}</Alert>}
        {success && <Alert kind="ok">چرخه با موفقیت بروزرسانی شد.</Alert>}

        <Card title="جزئیات چرخه">
          <div className="form-group">
            <label>نام چرخه</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="نام چرخه"
            />
          </div>

          <div className="form-group">
            <label>ترم</label>
            <input
              type="text"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="مثال: 1403-بهار"
            />
          </div>

          <div className="form-group">
            <label>تاریخ آغاز</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          <div className="row row-end mt-2" style={{ gap: 8 }}>
            <button
              className="btn btn--ghost"
              onClick={() => navigate(`/cycles/${id}`)}
              disabled={loading}
            >
              انصراف
            </button>
            <button
              className="btn btn--teal"
              onClick={handleUpdate}
              disabled={loading || !name.trim()}
            >
              {loading ? "درحال ذخیره..." : "ذخیره تغییرات"}
            </button>
          </div>
        </Card>

        <Card title="مدیریت پیشرفته" style={{ marginTop: 20 }}>
          <p className="small muted">بایگانی این چرخه را انجام دهید تا دیگر برای انتخاب در دستگاه‌ها در دسترس نباشد.</p>
          <div className="mt-2">
            <button
              className="btn btn--bad"
              onClick={handleArchive}
              disabled={loading}
            >
              {loading ? "درحال پردازش..." : "بایگانی چرخه"}
            </button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
