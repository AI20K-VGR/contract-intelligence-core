export const sampleSearchQuery =
  'Quy định về mức trần bồi thường thiệt hại và điều kiện áp dụng phạt vi phạm trong trường hợp gián đoạn dịch vụ SLA?'

export type SearchCitation = {
  id: number
  quote: string
  source: string
  confidence: string
  title: string
}

export const searchCitations: SearchCitation[] = [
  {
    id: 1,
    quote:
      '“Mức trần bồi thường thiệt hại tối đa không vượt quá 100% tổng giá trị dịch vụ thực tế mà bên sử dụng đã thanh toán trong 06 tháng liền kề.”',
    source: 'Điều 6.2 (Trang 12)',
    confidence: '99.2%',
    title: 'Xem nguồn [1]: Điều 6.2 - Trang 12',
  },
  {
    id: 2,
    quote:
      '“Chế tài phạt vi phạm và cam kết SLA được tạm hoãn trong thời hạn tối đa 72 giờ khi xảy ra Sự kiện Bất khả kháng.”',
    source: 'Điều 8.1 (Trang 18)',
    confidence: '98.6%',
    title: 'Xem nguồn [2]: Điều 8.1 - Trang 18',
  },
  {
    id: 3,
    quote:
      '“Bên B được miễn trừ hoàn toàn trách nhiệm đối với các tổn thất gián tiếp hoặc thiệt hại về cơ hội kinh doanh phát sinh ngoài hợp đồng.”',
    source: 'Điều 6.4 (Trang 14)',
    confidence: '97.8%',
    title: 'Xem nguồn [3]: Điều 6.4 - Trang 14',
  },
  {
    id: 4,
    quote:
      '“Thời gian tối đa khắc phục sự cố nghiêm trọng (MTTR) được quy định chi tiết kèm bảng tỷ lệ khấu trừ cước viễn thông.”',
    source: 'Phụ lục SLA (Trang 36)',
    confidence: '96.5%',
    title: 'Xem nguồn [4]: Phụ lục SLA - Trang 36',
  },
]

export const searchAnswerText = `Theo quy định tại hồ sơ hợp đồng dịch vụ viễn thông & CNTT, mức trần bồi thường thiệt hại được giới hạn không vượt quá 100% tổng giá trị dịch vụ thực tế mà bên sử dụng đã thanh toán trong 06 tháng liền kề trước thời điểm xảy ra sự cố. Đồng thời, các trường hợp đứt cáp quang biển hoặc sự kiện bất khả kháng diện rộng sẽ được tạm hoãn áp dụng chế tài tính phạt vi phạm SLA trong khoảng thời gian tối đa 72 giờ kể từ khi gửi thông báo bằng văn bản hoặc email hợp lệ.

Bên B được miễn trừ hoàn toàn trách nhiệm đối với các tổn thất gián tiếp, thiệt hại hệ quả hoặc mất doanh thu cơ hội kinh doanh ngoài phạm vi nghĩa vụ trực tiếp đã thỏa thuận. Tỷ lệ khấu trừ cụ thể và tiêu chuẩn thời gian khắc phục sự cố (MTTR) được quy định chi tiết tại Phụ lục cam kết chất lượng dịch vụ SLA.`
