export type SplitVerdict = 'none' | 'correct' | 'deviation' | 'edit'

export type SplitCitation = {
  id: number
  title: string
  quote: string
  source: string
  confidence: string
  page: number
  articleTitle: string
  clauses: Array<{
    heading: string
    body: string
    highlight?: boolean
  }>
  footerNote: string
  hash: string
}

export const splitSearchQuery =
  'Quy định về mức trần bồi thường thiệt hại và điều kiện áp dụng phạt...'

export const splitCitations: SplitCitation[] = [
  {
    id: 1,
    title: 'Hạn mức trần chi phí kỹ thuật',
    quote:
      '"Chi phí dự phòng phát sinh nâng cấp hạ tầng giai đoạn 1 được chốt mức trần là 550.000.000 VND (Năm trăm năm mươi triệu đồng), mọi chi phí vượt hạn mức phải có văn bản phê duyệt bổ sung của Bên A trước khi thực hiện."',
    source: 'Khoản 5.2 (Trang 3/24)',
    confidence: '99.4% (Khớp 100%)',
    page: 3,
    articleTitle:
      'ĐIỀU 5: GIÁ TRỊ HỢP ĐỒNG, ĐỒNG TIỀN THANH TOÁN VÀ PHƯƠNG THỨC QUYẾT TOÁN',
    clauses: [
      {
        heading: 'Khoản 5.1 (Tổng giá trị tạm tính):',
        body: 'Tổng giá trị hợp đồng dịch vụ triển khai và tích hợp giải pháp hệ thống CNTT lõi tạm tính là 28.450.000.000 VND (Bằng chữ: Hai mươi tám tỷ bốn trăm năm mươi triệu đồng chẵn). Mức giá này đã bao gồm toàn bộ thuế Giá trị gia tăng (VAT 10%), chi phí bản quyền license cho 2.500 nút mạng, bảo hiểm kỹ thuật và phí nhân công vận hành tại chỗ trong 12 tháng đầu tiên.',
      },
      {
        heading: 'Khoản 5.2 (Hạn mức trần và Chi phí dự phòng kỹ thuật):',
        body: '"Chi phí dự phòng phát sinh nâng cấp hạ tầng giai đoạn 1 được chốt mức trần là 550.000.000 VND (Năm trăm năm mươi triệu đồng), mọi chi phí vượt hạn mức phải có văn bản phê duyệt bổ sung của Bên A trước khi thực hiện."',
        highlight: true,
      },
      {
        heading: 'Khoản 5.3 (Lịch trình giải ngân theo SLA nghiệm thu):',
        body: 'Các bên thống nhất lịch thanh toán được phân bổ thành 04 đợt theo biên bản nghiệm thu chuyển giao công nghệ. Đợt 1 (30%) trong vòng 10 ngày làm việc kể từ ngày hợp đồng có hiệu lực và bảo lãnh tạm ứng được phát hành; Đợt 2 (35%) sau khi hoàn tất kiểm thử UAT hệ thống Core Gateway; Đợt 3 (25%) sau nghiệm thu Golive chính thức và bàn giao mã nguồn.',
      },
      {
        heading: 'Khoản 5.4 (Đồng tiền và phương thức chuyển khoản):',
        body: 'Mọi giao dịch tài chính liên quan đến phụ lục và khối lượng dịch vụ tăng thêm đều được định giá và thanh toán bằng Việt Nam Đồng (VND) thông qua tài khoản pháp nhân mở tại Ngân hàng TMCP Ngoại thương Việt Nam.',
      },
    ],
    footerNote: 'Trang 3 / 24',
    hash: '7f3b...9e1a',
  },
  {
    id: 2,
    title: 'Mức trần bồi thường thiệt hại',
    quote:
      '"Mức trần bồi thường thiệt hại không vượt quá 100% tổng giá trị dịch vụ thực tế đã thanh toán trong 06 tháng gần nhất trước thời điểm phát sinh sự kiện vi phạm..."',
    source: 'Khoản 6.2 (Trang 12)',
    confidence: '99.2%',
    page: 12,
    articleTitle: 'ĐIỀU 6: TRÁCH NHIỆM BỒI THƯỜNG VÀ GIỚI HẠN NGHĨA VỤ',
    clauses: [
      {
        heading: 'Khoản 6.1 (Các trường hợp vi phạm nghĩa vụ hợp đồng):',
        body: 'Trong trường hợp một trong hai Bên vi phạm bất kỳ cam kết, nghĩa vụ hoặc thỏa thuận nào quy định tại Hợp đồng này mà không khắc phục được trong thời hạn ba mươi (30) ngày kể từ ngày nhận được thông báo bằng văn bản từ Bên không vi phạm, Bên bị vi phạm có quyền áp dụng các chế tài theo thỏa thuận và quy định của pháp luật hiện hành.',
      },
      {
        heading: 'Khoản 6.2 (Giới hạn mức bồi thường tối đa):',
        body: '"Mức trần bồi thường thiệt hại không vượt quá 100% tổng giá trị dịch vụ thực tế đã thanh toán trong 06 tháng gần nhất trước thời điểm phát sinh sự kiện vi phạm."',
        highlight: true,
      },
      {
        heading: 'Khoản 6.3 (Thủ tục yêu cầu bồi thường):',
        body: 'Bên yêu cầu bồi thường phải gửi thông báo chi tiết bằng văn bản kèm theo các bằng chứng, hóa đơn, chứng từ hợp lệ chứng minh thiệt hại thực tế phát sinh trong thời hạn không quá bốn mươi lăm (45) ngày kể từ thời điểm phát hiện thiệt hại.',
      },
    ],
    footerNote: 'Trang 12 / 24',
    hash: '9fa8...e4a1',
  },
  {
    id: 3,
    title: 'Miễn trừ trách nhiệm tổn thất gián tiếp',
    quote:
      '"Bên B được miễn trừ hoàn toàn trách nhiệm đối với tổn thất gián tiếp hoặc thiệt hại cơ hội kinh doanh phát sinh do lỗi bên thứ ba cung cấp mạng truyền dẫn..."',
    source: 'Khoản 6.4 (Trang 14)',
    confidence: '97.8%',
    page: 14,
    articleTitle: 'ĐIỀU 6: TRÁCH NHIỆM BỒI THƯỜNG VÀ GIỚI HẠN NGHĨA VỤ',
    clauses: [
      {
        heading: 'Khoản 6.3 (Thủ tục yêu cầu bồi thường):',
        body: 'Bên yêu cầu bồi thường phải gửi thông báo chi tiết bằng văn bản kèm theo các bằng chứng hợp lệ chứng minh thiệt hại thực tế phát sinh.',
      },
      {
        heading:
          'Khoản 6.4 (Miễn trừ trách nhiệm đối với thiệt hại gián tiếp):',
        body: '"Bên B được miễn trừ hoàn toàn trách nhiệm đối với tổn thất gián tiếp hoặc thiệt hại cơ hội kinh doanh phát sinh do lỗi bên thứ ba cung cấp mạng truyền dẫn."',
        highlight: true,
      },
    ],
    footerNote: 'Trang 14 / 24',
    hash: 'c21d...4b90',
  },
  {
    id: 4,
    title: 'Tạm hoãn chế tài khi Bất khả kháng',
    quote:
      '"Chế tài phạt vi phạm và cam kết SLA được tạm hoãn tối đa 72 giờ khi xảy ra Bất khả kháng có xác nhận của cơ quan thẩm quyền..."',
    source: 'Khoản 8.1 (Trang 18)',
    confidence: '96.5%',
    page: 18,
    articleTitle: 'ĐIỀU 8: SỰ KIỆN BẤT KHẢ KHÁNG VÀ TẠM HOÃN NGHĨA VỤ',
    clauses: [
      {
        heading: 'Khoản 8.1 (Tạm hoãn chế tài khi Bất khả kháng):',
        body: '"Chế tài phạt vi phạm và cam kết SLA được tạm hoãn tối đa 72 giờ khi xảy ra Bất khả kháng có xác nhận của cơ quan thẩm quyền."',
        highlight: true,
      },
      {
        heading: 'Khoản 8.2 (Nghĩa vụ thông báo):',
        body: 'Bên viện dẫn sự kiện bất khả kháng phải thông báo bằng văn bản hoặc email hợp lệ trong vòng 24 giờ kể từ khi sự kiện phát sinh, kèm theo chứng từ của cơ quan có thẩm quyền.',
      },
    ],
    footerNote: 'Trang 18 / 24',
    hash: 'a77e...12c4',
  },
]

export const totalPdfPages = 24
