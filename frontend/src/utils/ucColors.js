export const UC_COLORS = {
  UCB:  '#003262', // Berkeley Blue
  UCD:  '#B58500', // Aggie Gold
  UCI:  '#0064A4', // UCI Blue
  UCLA: '#2774AE', // UCLA Blue
  UCM:  '#D4A017', // Merced Gold
  UCR:  '#003DA5', // Highlander Blue
  UCSB: '#FEBC11', // Gaucho Gold
  UCSC: '#DC4405', // Banana Slug Orange
  UCSD: '#182B49', // Triton Navy
}
export const UC_BLUE = '#1295D8'

/**
 * Returns the UC campus color for a given key, falling back to a
 * generic palette color if the key isn't a known campus.
 */
const FALLBACK_COLORS = [
  '#228be6', '#fa5252', '#40c057', '#fab005', '#7950f2',
  '#fd7e14', '#15aabf', '#e64980', '#82c91e', '#be4bdb',
]

export function getUCColor(key, index = 0) {
  return UC_COLORS[key] || FALLBACK_COLORS[index % FALLBACK_COLORS.length]
}
