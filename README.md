# UC Transfer Trends

A full-stack web app for exploring University of California transfer admission
data across all 9 campuses, 100+ majors, and 14 years (2012–2025).

## Overview

UC Transfer Trends helps future transfer students and researchers visualize how competitive UC admissions are by campus, major, and year. Data is sourced directly from official UC admissions reports and includes applicant counts, admit rates, yield rates, and GPA ranges.

## Features

- Look at admission trends by campus, major, and college/school
- Interactive charts and data tables with admit rates, GPA ranges, and yield rates
- Upload your unofficial transcript to match completed courses against UC transfer requirements
- View articulation agreements from community colleges to UCs
- Save, track, and compare majors you're interested in

## Images

**General Transfer Acceptance Rates**
<img width="1512" height="828" alt="Screenshot 2026-02-23 at 2 18 11 PM" src="https://github.com/user-attachments/assets/bc1fbd86-9f5a-4b98-8d95-e9afdf6eea4c" />

**Per Major Acceptance Rates**
<img width="1512" height="827" alt="Screenshot 2026-02-23 at 2 12 52 PM" src="https://github.com/user-attachments/assets/d97aabb0-2b73-4562-b44f-d0c15d2801c5" />

**Major Acceptance Rates Per UC Campus**
<img width="1512" height="828" alt="Screenshot 2026-02-23 at 2 11 13 PM" src="https://github.com/user-attachments/assets/14bd2c36-4845-4962-a733-45c2367a73e8" />

**College/School Acceptance Rates Per UC Campus**
<img width="1512" height="827" alt="Screenshot 2026-02-23 at 2 22 55 PM" src="https://github.com/user-attachments/assets/ed4cc1e4-0caa-4830-b110-52fdded09f56" />

## Tech Stack

| Layer      | Technology                        |
| ---------- | --------------------------------- |
| Frontend   | React, Vite, Mantine UI, Recharts |
| Backend    | Django                            |
| Database   | PostgreSQL                        |
| Scraper    | Playwright, httpx, Pydantic       |
| Deployment | Vercel, Render                    |

## Data Source

- Admission statistics from [Transfers by major | UC Admissions](https://www.universityofcalifornia.edu/about-us/information-center/transfers-major)
- Articulation agreements from [ASSIST.org](https://assist.org)
