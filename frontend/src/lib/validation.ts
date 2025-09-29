import { z } from 'zod';

// SSN validation schema
const ssnSchema = z.string()
  .regex(/^\d{9}$/, 'SSN must be exactly 9 digits')
  .transform(val => val.replace(/\D/g, '')); // Remove any non-digits

// Name validation schema
const nameSchema = z.string()
  .min(1, 'Name is required')
  .max(50, 'Name must be less than 50 characters')
  .regex(/^[a-zA-Z\s\-']+$/, 'Name can only contain letters, spaces, hyphens, and apostrophes');

// Optional name schema
const optionalNameSchema = nameSchema.optional().or(z.literal(''));

// Date validation
const dateSchema = z.date()
  .refine(date => date <= new Date(), 'Date cannot be in the future');

// Form validation schema
export const formValidationSchema = z.object({
  firstName: nameSchema,
  lastName: nameSchema,
  middleName: optionalNameSchema,
  suffix: optionalNameSchema,
  ssn: ssnSchema,
  dateOfBirth: dateSchema.refine(
    date => {
      const age = (new Date().getTime() - date.getTime()) / (365.25 * 24 * 60 * 60 * 1000);
      return age >= 16 && age <= 120;
    },
    'Date of birth must represent an age between 16 and 120 years'
  ),
  activeDutyDate: z.date(),
}).refine(
  data => data.activeDutyDate >= data.dateOfBirth,
  {
    message: 'Active duty date cannot be before date of birth',
    path: ['activeDutyDate'],
  }
);

export type FormValidation = z.infer<typeof formValidationSchema>;

// API request validation
export const verifyRequestSchema = z.object({
  firstName: nameSchema,
  lastName: nameSchema,
  middleName: optionalNameSchema,
  suffix: optionalNameSchema,
  ssn: ssnSchema,
  dateOfBirth: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format'),
  activeDutyDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format'),
});

export type VerifyRequestValidation = z.infer<typeof verifyRequestSchema>;