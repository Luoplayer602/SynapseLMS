export type Language = 'vi' | 'en'
const labels: Record<string, [string, string]> = {
  login: ['Đăng nhập', 'Sign in'], register: ['Đăng ký', 'Register'], logout: ['Đăng xuất', 'Sign out'],
  email: ['Email', 'Email'], password: ['Mật khẩu', 'Password'], name: ['Họ và tên', 'Full name'],
  center: ['Trung tâm', 'Center'], invite: ['Mã mời', 'Invite code'], useInvite: ['Dùng mã mời', 'Use invite code'],
  loading: ['Đang tải…', 'Loading…'], profile: ['Hồ sơ', 'Profile'], members: ['Thành viên', 'Members'],
  centers: ['Trung tâm', 'Centers'], role: ['Vai trò', 'Role'], save: ['Lưu', 'Save'], create: ['Tạo mới', 'Create'],
  reason: ['Lý do', 'Reason'], active: ['Hoạt động', 'Active'], inactive: ['Tạm khóa', 'Suspended'],
  organization_manager: ['Quản lý trung tâm', 'Center manager'], staff: ['Giáo vụ / Tư vấn', 'Staff / Advisor'],
  teacher: ['Giáo viên', 'Teacher'], student: ['Học viên', 'Student'], root: ['Quản trị hệ thống', 'Root Admin'],
  welcome: ['Chào mừng đến SynapseLMS', 'Welcome to SynapseLMS'],
  intro: ['Không gian học tập và quản lý trung tâm ngoại ngữ.', 'Your language learning and center workspace.'],
  registered: ['Đã tạo tài khoản. Bạn có thể đăng nhập.', 'Account created. You can sign in now.'],
  noCenters: ['Chưa có trung tâm mở đăng ký. Bạn có thể dùng mã mời.', 'No centers are open for registration. You can use an invite code.'],
  choose: ['Chọn trung tâm', 'Select a center'], passwordHint: ['12–128 ký tự', '12–128 characters'],
  support: ['Mở phiên hỗ trợ', 'Start support session'], endSupport: ['Kết thúc hỗ trợ', 'End support session'],
  supporting: ['Đang hỗ trợ trung tâm', 'Supporting center'], public: ['Hiển thị công khai', 'Public listing'],
  registration: ['Cho phép đăng ký', 'Allow registration'], slug: ['Mã trung tâm', 'Center code'],
  unavailable: ['Trung tâm hoặc quyền thành viên hiện không hoạt động.', 'Your center or membership is currently unavailable.'],
  empty: ['Chưa có dữ liệu.', 'No records yet.'], updated: ['Đã lưu thay đổi.', 'Changes saved.'],
  newMember: ['Thêm thành viên', 'Add member'], newCenter: ['Thêm trung tâm', 'Add center'],
  createInvite: ['Tạo mã mời học viên (1 lượt, 7 ngày)', 'Create student invite (1 use, 7 days)'],
  passwordChange: ['Đổi mật khẩu', 'Change password'], currentPassword: ['Mật khẩu hiện tại', 'Current password'],
  newPassword: ['Mật khẩu mới', 'New password'], passwordChanged: ['Đã đổi mật khẩu. Hãy đăng nhập lại.', 'Password changed. Please sign in again.'],
  retry: ['Thử lại', 'Retry'], lockUser: ['Khóa tài khoản', 'Disable account'], unlockUser: ['Mở tài khoản', 'Enable account'],
}
export function translate(language: Language, key: string): string {
  return labels[key]?.[language === 'vi' ? 0 : 1] || key
}
const errors: Record<string, [string, string]> = {
  INVALID_CREDENTIALS: ['Email hoặc mật khẩu không đúng.', 'Incorrect email or password.'],
  INVALID_SESSION: ['Phiên đã hết hiệu lực. Hãy đăng nhập lại.', 'Session expired. Please sign in again.'],
  ACCOUNT_CONFLICT: ['Email đã được sử dụng.', 'Email is already in use.'],
  REGISTRATION_UNAVAILABLE: ['Trung tâm hoặc mã mời không hợp lệ.', 'The center or invitation is unavailable.'],
  VALIDATION_ERROR: ['Kiểm tra lại thông tin đã nhập.', 'Please check the entered information.'],
  FORBIDDEN: ['Bạn không có quyền thực hiện thao tác này.', 'You do not have permission for this action.'],
  RATE_LIMITED: ['Quá nhiều yêu cầu. Vui lòng thử lại sau một phút.', 'Too many requests. Try again in a minute.'],
  TENANT_UNAVAILABLE: ['Trung tâm hoặc quyền thành viên không hoạt động.', 'Your center or membership is unavailable.'],
  SUPPORT_SESSION_REQUIRED: ['Phiên hỗ trợ đã hết hạn hoặc chưa được mở.', 'Start a new support session to continue.'],
  RESOURCE_CONFLICT: ['Dữ liệu bị trùng hoặc có thay đổi xung đột.', 'Duplicate or conflicting data.'],
}
export function errorMessage(language: Language, code: string) {
  return errors[code]?.[language === 'vi' ? 0 : 1] || (language === 'vi' ? 'Không thể hoàn tất yêu cầu. Vui lòng thử lại.' : 'Could not complete the request. Please retry.')
}
