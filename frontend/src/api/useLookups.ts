import { useQuery } from '@tanstack/react-query'
import { api } from './client'
import type { LookupMap } from './types'

const EMPTY: LookupMap = {
  campaign_type: [],
  campaign_intent: [],
  credit_segment: [],
  campaign_status: [],
  campaign_channel: [],
  message_tone: [],
  compliance_overall_verdict: [],
  compliance_check_result: [],
}

export function useLookups(): LookupMap {
  const { data } = useQuery({
    queryKey: ['lookups'],
    queryFn: api.getLookups,
    staleTime: 5 * 60 * 1000,   // 5 min — lookup values change rarely
    gcTime:    30 * 60 * 1000,  // keep in memory 30 min
  })
  return data ?? EMPTY
}
