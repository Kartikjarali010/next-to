import { api, fmtDay } from "../../api";
import { Badge, ErrorBox, Spinner, useAsync, useToast } from "../../components";
import { PageHead } from "../../components/adminui";

export default function Moderation() {
  const toast = useToast();
  const rv = useAsync(() => api<any[]>("/admin/reviews"));
  const us = useAsync(() => api<any[]>("/admin/users"));

  const hide = async (id: number) => {
    try { await api(`/admin/reviews/${id}/hide`, { method: "POST", body: {} }); toast("Review hidden"); rv.reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const suspend = async (id: number, suspended: boolean) => {
    try { await api(`/admin/users/${id}/suspend?suspended=${suspended}`, { method: "POST", body: {} }); toast(suspended ? "User suspended" : "User reinstated"); us.reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div className="stack">
      <PageHead title="Moderation" />
      <h2>Reviews</h2>
      {rv.loading ? <Spinner /> : rv.error ? <ErrorBox error={rv.error} retry={rv.reload} /> :
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Customer</th><th>Merchant</th><th>Rating</th><th>Comment</th><th>Date</th><th /></tr></thead>
          <tbody>{rv.data?.map((r) => (
            <tr key={r.id}>
              <td>{r.consumer_name}</td><td>{r.merchant_name}</td><td>{"★".repeat(r.rating)}</td><td>{r.comment || "—"}</td><td className="small">{fmtDay(r.created_at)}</td>
              <td>{r.hidden ? <span className="badge">hidden</span> : <button className="btn sm danger" onClick={() => hide(r.id)}>Hide</button>}</td>
            </tr>))}
            {!rv.data?.length && <tr><td colSpan={6} className="muted center">No reviews</td></tr>}</tbody>
        </table></div>}
      <h2 style={{ marginTop: 12 }}>Users</h2>
      {us.loading ? <Spinner /> : us.error ? <ErrorBox error={us.error} retry={us.reload} /> :
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Joined</th><th>State</th><th /></tr></thead>
          <tbody>{us.data?.map((u) => (
            <tr key={u.id}>
              <td>{u.name}</td><td>{u.email}</td><td><Badge s={u.role} /></td><td className="small">{fmtDay(u.created_at)}</td>
              <td>{u.suspended ? <span className="badge err">suspended</span> : <span className="badge ok">ok</span>}</td>
              <td>{u.role !== "admin" && (u.suspended
                ? <button className="btn sm light" onClick={() => suspend(u.id, false)}>Reinstate</button>
                : <button className="btn sm danger" onClick={() => suspend(u.id, true)}>Suspend</button>)}</td>
            </tr>))}</tbody>
        </table></div>}
    </div>
  );
}
