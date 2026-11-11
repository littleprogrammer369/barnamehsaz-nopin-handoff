/**
 * Offering resource selection: assign canonical room and instructor.
 * Q12: Each offering-unit participates in ONE resource nomination per unit.
 * Shared offerings (multiple units) require explicit per-unit nomination.
 */
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { Offerings, Resources } from "../lib/client";
import { useQuery } from "../lib/useQuery";
import { Card, Loading, ErrorState, Alert } from "../components/ui";

export function OfferingResourceSelection() {
  const { offeringId, unitId } = useParams();
  const navigate = useNavigate();
  const offId = Number(offeringId);
  const uId = Number(unitId);

  const offeringQ = useQuery(() => Offerings.get(offId), [offId]);
  const roomsQ = useQuery(() => Resources.list("room"), []);
  const instructorsQ = useQuery(() => Resources.list("instructor"), []);

  const [selectedRoom, setSelectedRoom] = useState<number | null>(null);
  const [selectedInstructor, setSelectedInstructor] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (offeringQ.loading || roomsQ.loading || instructorsQ.loading) {
    return <AppShell title="انتخاب منابع"><Loading /></AppShell>;
  }

  if (offeringQ.error || !offeringQ.data) {
    return <AppShell title="انتخاب منابع"><ErrorState message={offeringQ.error ?? "دستگاه یافت نشد"} onRetry={offeringQ.reload} /></AppShell>;
  }

  const offering = offeringQ.data;

  const handleSave = async () => {
    setLoading(true);
    setError(null);
    try {
      await fetch(`/api/v1/phase2/offerings/${offId}/units/${uId}/resources`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          room_resource_id: selectedRoom,
          instructor_resource_id: selectedInstructor,
        }),
      }).then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      });
      
      navigate(`/offerings/${offId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "خطای نامشخص");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell title={`انتخاب منابع: دستگاه #${offId}`}>
      <div className="mt-2">
        <Card title="انتخاب کلاس و استاد">
          {error && <Alert kind="bad">{error}</Alert>}
          
          <div className="form-group">
            <label>کلاس</label>
            <select value={selectedRoom ?? ""} onChange={(e) => setSelectedRoom(e.target.value ? Number(e.target.value) : null)}>
              <option value="">— بدون انتخاب —</option>
              {(roomsQ.data ?? []).map(r => (
                <option key={r.id} value={r.id}>{r.name} ({r.capacity})</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>استاد</label>
            <select value={selectedInstructor ?? ""} onChange={(e) => setSelectedInstructor(e.target.value ? Number(e.target.value) : null)}>
              <option value="">— بدون انتخاب —</option>
              {(instructorsQ.data ?? []).map(i => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </select>
          </div>

          <div className="row row-end mt-2" style={{ gap: 8 }}>
            <button className="btn btn--ghost" onClick={() => navigate(`/offerings/${offId}`)}>انصراف</button>
            <button className="btn btn--teal" onClick={handleSave} disabled={loading}>
              {loading ? "درحال ذخیره..." : "ذخیره"}
            </button>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
