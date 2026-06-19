export const HOME_COMPANY = "Celonis";

/**
 * Whether a company label refers to Celonis itself (vs. a tracked
 * competitor). Used to consistently highlight our own brand wherever
 * competitors are listed side by side — color chips, diversity bars,
 * fonts, logos, etc.
 */
export function isHomeCompany(company: string): boolean {
  return company.trim().toLowerCase() === HOME_COMPANY.toLowerCase();
}
