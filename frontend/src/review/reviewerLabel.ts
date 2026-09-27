type ReviewerIdentity = {
  reviewerName: string | null
  reviewerEmail: string | null
  reviewerId: string
}

export function reviewerLabel(entry: ReviewerIdentity) {
  const name = entry.reviewerName?.trim() ?? ''
  const email = entry.reviewerEmail?.trim() ?? ''
  if (name && email && name.toLowerCase() !== email.toLowerCase()) {
    return `${name} · ${email}`
  }
  return name || email || entry.reviewerId
}
