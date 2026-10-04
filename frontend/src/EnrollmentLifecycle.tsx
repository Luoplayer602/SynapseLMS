import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import { createRequestKey, requestErrorCode } from './requestKey'
import { BusinessForm } from './Admissions'
import type { Language } from './i18n'
import { BusinessPage } from './ui/BusinessPage'
import { errorMessage } from './i18n'

type Props = { language: Language; staff: boolean; manager?: boolean }
type Session = { id: string; starts_at: string; ends_at: string; timezone: string }
type Calculation = { total: number; paid: number; remaining: number; unused: number; fee: number; total_sessions: number; unused_sessions: number }
type Quote = Calculation & { source_digest: string; proposed: number; offset_amount: number; cash_amount: number }
type Refund = { id: string; status: string; version: number; proposed: number; approved: number; offset_amount: number; cash_amount: number; calculation: Calculation; reason?: string; disbursement: { amount: number; method: string; reference: string; created_at: string } | null }
type Row = { id: string; enrollment_id: string | null; student_name: string; course_name: string; class_name: string | null; state: string; version: number; settled: boolean; periods: { starts_at: string; ends_at: string | null }[] }
type Detail = Row & { sessions: Session[]; refunds: Refund[]; history: { id: string; action: string; effective_at: string; reason?: string }[]; invoice: { total: number; paid: number; remaining: number; offset: number } }
type Policy = { kind: string; value: number; version: number }
const words: Record<string, [string, string]> = {
  title: ['Bảo lưu & hoàn phí', 'Enrollment & refunds'], refresh: ['Làm mới', 'Refresh'], loading: ['Đang tải…', 'Loading…'], empty: ['Chưa có dữ liệu.', 'No records.'], details: ['Chi tiết', 'Details'], next: ['Sau', 'Next'], previous: ['Trước', 'Previous'],
  active: ['Đang học / đã xếp', 'Active / placed'], suspended: ['Đã ghi nhận bảo lưu', 'Suspension recorded'], cancelled: ['Đã hủy', 'Cancelled'], waiting: ['Chờ xếp lớp', 'Waiting for placement'], suspend: ['Bảo lưu', 'Suspend'], cancel: ['Hủy đăng ký', 'Cancel enrollment'], resume: ['Tiếp tục cùng lớp', 'Resume in this class'], action: ['Thao tác', 'Action'], session: ['Buổi bắt đầu áp dụng', 'Effective session'], reason: ['Lý do nội bộ', 'Internal reason'], preview: ['Xem trước tác động', 'Preview impact'], confirm: ['Xác nhận thay đổi quyền học', 'Confirm enrollment change'], periods: ['Khoảng có quyền học (không gồm mốc kết thúc)', 'Learning periods (end excluded)'], open: ['Đến hết lịch lớp', 'Through the class schedule'], history: ['Lịch sử', 'History'],
  hint: ['Mốc tương lai chỉ dừng quyền học từ giờ bắt đầu buổi đã chọn. Bảo lưu không giữ chỗ, không tự bù buổi hoặc dừng trả góp. Tiếp tục chỉ được trước khi duyệt hoàn.', 'A future boundary takes effect at the selected session start. Suspension does not reserve seats, replace missed sessions or stop installments. Resume is available only before refund approval.'],
  remainingSnapshot: ['Công nợ tại lúc lập đề xuất', 'Outstanding when proposed'], affectedSessions: ['Các buổi từ mốc áp dụng', 'Sessions from the effective boundary'], affected: ['Buổi chưa học / tổng buổi tính phí', 'Unused / billable sessions'], total: ['Học phí ròng', 'Net tuition'], paid: ['Đã thu hợp lệ', 'Valid receipts'], remaining: ['Còn phải trả', 'Outstanding'], unused: ['Giá trị chưa học', 'Unused value'], fee: ['Phí khấu trừ', 'Deduction'], proposed: ['Đề xuất hoàn', 'Proposed refund'], offset: ['Bù trừ công nợ', 'Debt offset'], cash: ['Tiền phải chi', 'Cash to return'], refunded: ['Đã ghi nhận chi', 'Disbursement recorded'],
  quote: ['Tính đề xuất hoàn', 'Calculate refund'], create: ['Lưu đề xuất hoàn', 'Save refund proposal'], approve: ['Duyệt quyết toán', 'Approve settlement'], reject: ['Từ chối đề xuất', 'Reject proposal'], cancelProposal: ['Hủy đề xuất', 'Cancel proposal'], amount: ['Khoản hoàn được duyệt (VND)', 'Approved refund (VND)'], reasonHint: ['Bắt buộc lý do nếu điều chỉnh khác đề xuất hoặc từ chối/hủy.', 'A reason is required for an override, rejection or cancellation.'], pending: ['Đã duyệt, chờ chi', 'Approved, awaiting payment'], proposedStatus: ['Chờ duyệt hoàn', 'Proposed'], paidStatus: ['Đã quyết toán', 'Settled'], rejected: ['Đã từ chối', 'Rejected'], no_refund: ['Không hoàn phí', 'No refund'], disburse: ['Ghi nhận đã trả tiền', 'Record money returned'], method: ['Phương thức', 'Method'], cashMethod: ['Tiền mặt', 'Cash'], transfer: ['Chuyển khoản', 'Bank transfer'], reference: ['Tham chiếu', 'Reference'], paidHint: ['Chỉ xác nhận khi đã trả tiền bên ngoài. Hệ thống không chuyển tiền ngân hàng. Không sửa/xóa khoản hoàn đã ghi nhận.', 'Confirm only after money has been returned externally. This system does not transfer money. Recorded settlements cannot be edited or deleted.'],
  policy: ['Chính sách khấu trừ hoàn phí', 'Refund deduction policy'], fixed: ['Số tiền VND', 'Fixed VND'], percent: ['Phần trăm', 'Percentage'], value: ['Mức khấu trừ', 'Deduction value'], savePolicy: ['Lưu chính sách hoàn phí', 'Save refund policy'], settled: ['Đã quyết toán: không tiếp tục học hoặc đảo khoản thu của hóa đơn này.', 'Settled: resumption and receipt reversal are unavailable for this invoice.'],
}
const word = (l: Language, key: string) => words[key]?.[l === 'vi' ? 0 : 1] || key
const money = (n: number) => new Intl.NumberFormat('vi-VN').format(n) + ' VND'
const instant = (s: string, l: Language) => new Date(s).toLocaleString(l === 'vi' ? 'vi-VN' : 'en-GB')
function useData<T>(path: string) {
  const [data, setData] = useState<T>(), [error, setError] = useState<unknown>()
  useEffect(() => { let active = true; api<T>(path).then(x => { if (active) setData(x) }).catch(e => { if (active) setError(e) }); return () => { active = false } }, [path])
  return { data, error }
}
function Failure({ language, error }: { language: Language; error: unknown }) { return <p role="alert">{errorMessage(language, requestErrorCode(error, 'NETWORK_ERROR'))}</p> }
function CalculationView({ language, data }: { language: Language; data: Calculation }) {
  return <dl>{(['total', 'paid', 'remaining', 'unused', 'fee'] as const).map(k => <div key={k}><dt>{word(language, k === 'remaining' ? 'remainingSnapshot' : k)}</dt><dd>{money(data[k])}</dd></div>)}<dt>{word(language, 'affected')}</dt><dd>{data.unused_sessions} / {data.total_sessions}</dd></dl>
}
function Operation({ language, data, done }: { language: Language; data: Detail; done: () => void }) {
  const [action, setAction] = useState(data.state === 'waiting' ? 'cancel' : data.state === 'suspended' ? 'resume' : 'suspend')
  const [session, setSession] = useState(''), [reason, setReason] = useState(''), [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<{ source_digest: string; total_sessions: number; unused_sessions: number; effective_at?: string; sessions?: { id: string; starts_at: string; status: string }[] }>(), [error, setError] = useState<unknown>()
  const body = { action, session_id: session || null, version: data.version, reason }
  async function inspect(e: FormEvent) { e.preventDefault(); if (busy) return; setBusy(true); setError(undefined); setPreview(undefined); try { setPreview(await api(`/enrollments/${data.id}/preview`, 'POST', { ...body, request_key: createRequestKey() })) } catch (e) { setError(e) } finally { setBusy(false) } }
  return <><p>{word(language, 'hint')}</p><form className="card compact-form" onSubmit={inspect}><fieldset disabled={busy}>
    <label>{word(language, 'action')}<select value={action} onChange={e => { setAction(e.target.value); setPreview(undefined) }}>{(data.state === 'waiting' ? ['cancel'] : data.state === 'suspended' ? ['resume', 'cancel'] : ['suspend', 'cancel']).map(k => <option key={k} value={k}>{word(language, k)}</option>)}</select></label>
    {data.enrollment_id && <label>{word(language, 'session')}<select required value={session} onChange={e => { setSession(e.target.value); setPreview(undefined) }}><option value="">—</option>{data.sessions.map(s => <option key={s.id} value={s.id}>{instant(s.starts_at, language)} — {s.timezone}</option>)}</select></label>}
    <label>{word(language, 'reason')}<input required minLength={3} maxLength={500} value={reason} onChange={e => { setReason(e.target.value); setPreview(undefined) }} /></label><button>{word(language, 'preview')}</button></fieldset></form>
    {error && <Failure language={language} error={error} />}{preview && <BusinessForm key={preview.source_digest} language={language} title={word(language, 'confirm')} path={`/enrollments/${data.id}/operations`} body={() => ({ ...body, source_digest: preview.source_digest })} onDone={done}><p>{word(language, action)} · {preview.effective_at && instant(preview.effective_at, language)}</p><p>{word(language, 'affected')}: {preview.unused_sessions} / {preview.total_sessions}</p>{preview.effective_at && <details><summary>{word(language, 'affectedSessions')}</summary><ul>{preview.sessions?.filter(s => s.status === 'scheduled' && s.starts_at >= preview.effective_at!).map(s => <li key={s.id}>{instant(s.starts_at, language)}</li>)}</ul></details>}</BusinessForm>}</>
}
function RefundProposal({ language, id, done }: { language: Language; id: string; done: () => void }) {
  const [quote, setQuote] = useState<Quote>(), [error, setError] = useState<unknown>(), [busy, setBusy] = useState(false)
  async function inspect() { if (busy) return; setBusy(true); setError(undefined); setQuote(undefined); try { setQuote(await api('/refunds/preview', 'POST', { request_id: id, request_key: createRequestKey() })) } catch (e) { setError(e) } finally { setBusy(false) } }
  return <><button disabled={busy} onClick={inspect}>{word(language, 'quote')}</button>{error && <Failure language={language} error={error} />}{quote && <BusinessForm key={quote.source_digest} language={language} title={word(language, 'create')} path="/refunds" body={() => ({ request_id: id, source_digest: quote.source_digest })} onDone={done}><CalculationView language={language} data={quote} /><p>{word(language, 'proposed')}: {money(quote.proposed)} · {word(language, 'offset')}: {money(quote.offset_amount)} · {word(language, 'cash')}: {money(quote.cash_amount)}</p></BusinessForm>}</>
}
function RefundCard({ language, staff, row, done }: Props & { row: Refund; done: () => void }) {
  const [amount, setAmount] = useState(row.proposed), [decision, setDecision] = useState('approve')
  return <article className="card"><h3>{word(language, row.status === 'proposed' ? 'proposedStatus' : row.status === 'paid' ? 'paidStatus' : row.status)}</h3><CalculationView language={language} data={row.calculation} /><p>{word(language, 'proposed')}: {money(row.proposed)} · {word(language, 'amount')}: {money(row.approved)}</p><p>{word(language, 'offset')}: {money(row.offset_amount)} · {word(language, 'cash')}: {money(row.cash_amount)}</p>{row.reason && <p>{row.reason}</p>}
    {staff && row.status === 'proposed' && <BusinessForm language={language} title={word(language, 'approve')} path={`/refunds/${row.id}/decision`} body={f => ({ version: row.version, action: f.get('decision'), amount: Number(f.get('amount')), reason: f.get('reason') })} onDone={done}><label>{word(language, 'action')}<select name="decision" value={decision} onChange={e => setDecision(e.target.value)}>{['approve', 'reject', 'cancel'].map(k => <option key={k} value={k}>{word(language, k === 'cancel' ? 'cancelProposal' : k)}</option>)}</select></label><label>{word(language, 'amount')}<input name="amount" type="number" min={0} max={row.calculation.paid} step={1} required value={amount} onChange={e => setAmount(Number(e.target.value))} /></label><label>{word(language, 'reason')}<input name="reason" maxLength={500} /></label><p>{word(language, 'reasonHint')}</p>{decision === 'approve' && <p role="status">{word(language, 'offset')}: {money(Math.min(amount, row.calculation.remaining))} · {word(language, 'cash')}: {money(Math.max(0, amount - row.calculation.remaining))}</p>}</BusinessForm>}
    {staff && row.status === 'pending' && <BusinessForm language={language} title={word(language, 'disburse')} path={`/refunds/${row.id}/disburse`} body={f => ({ version: row.version, method: f.get('method'), reference: f.get('reference') })} onDone={done}><p>{word(language, 'paidHint')}</p><strong>{money(row.cash_amount)}</strong><label>{word(language, 'method')}<select name="method"><option value="cash">{word(language, 'cashMethod')}</option><option value="transfer">{word(language, 'transfer')}</option></select></label><label>{word(language, 'reference')}<input name="reference" maxLength={200} /></label></BusinessForm>}
    {row.disbursement && <p>{word(language, 'refunded')}: {money(row.disbursement.amount)} · {word(language, row.disbursement.method === 'cash' ? 'cashMethod' : 'transfer')} · {row.disbursement.reference} · {instant(row.disbursement.created_at, language)}</p>}
  </article>
}
function EnrollmentDetail({ language, staff, id, done }: Props & { id: string; done: () => void }) {
  const { data, error } = useData<Detail>(`/enrollments/${id}`)
  if (error) return <Failure language={language} error={error} />
  if (!data) return <p role="status">{word(language, 'loading')}</p>
  return <><h3>{word(language, 'periods')}</h3>{data.periods.map((p, i) => <p key={i}>{instant(p.starts_at, language)} → {p.ends_at ? instant(p.ends_at, language) : word(language, 'open')}</p>)}<p>{word(language, 'remaining')}: {money(data.invoice.remaining)} · {word(language, 'offset')}: {money(data.invoice.offset)}</p>
    {data.settled && <p>{word(language, 'settled')}</p>}{staff && !data.settled && data.state !== 'cancelled' && <Operation language={language} data={data} done={done} />}
    {staff && !data.settled && ['suspended', 'cancelled'].includes(data.state) && !data.refunds.some(r => r.status === 'proposed') && <RefundProposal language={language} id={id} done={done} />}
    {data.refunds.map(row => <RefundCard key={row.id} language={language} staff={staff} row={row} done={done} />)}
    <details><summary>{word(language, 'history')}</summary>{data.history.map(h => <p key={h.id}>{word(language, h.action)} · {instant(h.effective_at, language)} {h.reason}</p>)}</details></>
}
function PolicyEditor({ language, manager, done }: { language: Language; manager: boolean; done: () => void }) {
  const { data, error } = useData<Policy>('/refunds/policy')
  if (error) return <Failure language={language} error={error} />
  if (!data) return null
  return <details><summary>{word(language, 'policy')}</summary><p>{word(language, data.kind)}: {data.value}</p>{manager && <BusinessForm language={language} title={word(language, 'savePolicy')} path="/refunds/policy" method="PUT" body={f => ({ version: data.version, kind: f.get('kind'), value: Number(f.get('value')) })} onDone={done}><label>{word(language, 'method')}<select name="kind" defaultValue={data.kind}><option value="fixed">{word(language, 'fixed')}</option><option value="percent">{word(language, 'percent')}</option></select></label><label>{word(language, 'value')}<input name="value" type="number" min={0} max={1000000000} step={1} required defaultValue={data.value} /></label></BusinessForm>}</details>
}
function Listing({ language, staff, manager, refresh }: Props & { refresh: () => void }) {
  const [selected, setSelected] = useState(''), [offset, setOffset] = useState(0)
  return <>{staff && <PolicyEditor language={language} manager={!!manager} done={refresh} />}<ListPage key={offset} language={language} staff={staff} offset={offset} setOffset={setOffset} selected={selected} setSelected={setSelected} done={refresh} /></>
}
function ListPage({ language, staff, offset, setOffset, selected, setSelected, done }: Props & { offset: number; setOffset: (n: number) => void; selected: string; setSelected: (s: string) => void; done: () => void }) {
  const { data, error } = useData<{ items: Row[]; total: number }>(`/enrollments?offset=${offset}`)
  if (error) return <Failure language={language} error={error} />
  if (!data) return <p role="status">{word(language, 'loading')}</p>
  return <>{!data.items.length && <p>{word(language, 'empty')}</p>}{data.items.map(row => <article className="card" key={row.id}><h2>{row.student_name} — {row.course_name}</h2><p>{row.class_name} · {word(language, row.state)}</p><button onClick={() => setSelected(selected === row.id ? '' : row.id)}>{word(language, 'details')}</button>{selected === row.id && <EnrollmentDetail language={language} staff={staff} id={row.id} done={done} />}</article>)}<button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 20))}>{word(language, 'previous')}</button><button disabled={offset + 20 >= data.total} onClick={() => setOffset(offset + 20)}>{word(language, 'next')}</button></>
}
export function EnrollmentLifecycle(props: Props) {
  const [revision, setRevision] = useState(0)
  const refresh = () => setRevision(n => n + 1)
  return <BusinessPage title={<>{word(props.language, 'title')}</>} className="workflow-page" actions={<button onClick={refresh}>{word(props.language, 'refresh')}</button>}><Listing key={revision} {...props} refresh={refresh} /></BusinessPage>
}
