/**
 * Formats a Date object to YYYYMMDD string format
 */
export function formatDateToYYYYMMDD(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}${month}${day}`;
}

/**
 * Formats a Date object to YYYY-MM-DD string format
 */
export function formatDateToISO(date: Date): string {
  return date.toISOString().split('T')[0];
}

/**
 * Parses YYYYMMDD string to Date object
 */
export function parseDateFromYYYYMMDD(dateString: string): Date | null {
  if (!/^\d{8}$/.test(dateString)) {
    return null;
  }
  
  const year = parseInt(dateString.substring(0, 4));
  const month = parseInt(dateString.substring(4, 6)) - 1; // Month is 0-indexed
  const day = parseInt(dateString.substring(6, 8));
  
  const date = new Date(year, month, day);
  
  // Validate the date
  if (date.getFullYear() !== year || 
      date.getMonth() !== month || 
      date.getDate() !== day) {
    return null;
  }
  
  return date;
}

/**
 * Formats a date string for display (MM/DD/YYYY)
 */
export function formatDateForDisplay(dateString: string | null): string {
  if (!dateString) return 'Not specified';
  
  const date = parseDateFromYYYYMMDD(dateString);
  if (!date) return 'Invalid date';
  
  return date.toLocaleDateString('en-US');
}

/**
 * Gets today's date in YYYYMMDD format
 */
export function getTodayYYYYMMDD(): string {
  return formatDateToYYYYMMDD(new Date());
}

/**
 * Validates if a date string is in the future
 */
export function isDateInFuture(dateString: string): boolean {
  const date = parseDateFromYYYYMMDD(dateString);
  if (!date) return false;
  
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  return date > today;
}

/**
 * Calculates age from date of birth
 */
export function calculateAge(dateOfBirth: Date): number {
  const today = new Date();
  let age = today.getFullYear() - dateOfBirth.getFullYear();
  const monthDiff = today.getMonth() - dateOfBirth.getMonth();
  
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dateOfBirth.getDate())) {
    age--;
  }
  
  return age;
}

/**
 * Formats a Date object to MM/DD/YYYY string format
 */
export function formatDateToMMDDYYYY(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const year = date.getFullYear();
  return `${month}/${day}/${year}`;
}