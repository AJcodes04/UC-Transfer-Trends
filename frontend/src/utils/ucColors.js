export const UC_COLORS = {
  UCB:  '#003262',
  UCD:  '#B58500',
  UCI:  '#0064A4',
  UCLA: '#2774AE',
  UCM:  '#D4A017',
  UCR:  '#003DA5',
  UCSB: '#FEBC11',
  UCSC: '#DC4405',
  UCSD: '#182B49',
}
export const UC_BLUE = '#1295D8'

const FALLBACK_COLORS = [
  '#228be6', '#fa5252', '#40c057', '#fab005', '#7950f2',
  '#fd7e14', '#15aabf', '#e64980', '#82c91e', '#be4bdb',
]

export function getUCColor(key, index = 0) {
  return UC_COLORS[key] || FALLBACK_COLORS[index % FALLBACK_COLORS.length]
}
