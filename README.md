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
<img width="1512" height="860" alt="Screenshot 2026-03-31 at 1 27 51 PM" src="https://github.com/user-attachments/assets/019d152a-ff4b-4081-a222-7e1137fac6fe" />

**Per Major Acceptance Rates**
<img width="1511" height="861" alt="Screenshot 2026-03-31 at 1 30 08 PM" src="https://github.com/user-attachments/assets/a71eb08e-b090-4de7-b095-ec2cdc689d2a" />


**Major GPA Ranges/Acceptance Rates Per UC Campus**
<img width="1510" height="862" alt="Screenshot 2026-03-31 at 1 31 01 PM" src="https://github.com/user-attachments/assets/3721cc92-0664-4843-acf4-6d4f093e6a14" />

**Transfer Requirments**
<img width="1512" height="861" alt="Screenshot 2026-03-31 at 1 22 35 PM" src="https://github.com/user-attachments/assets/e5b909f8-8d28-415d-98bb-4bc41e7deaab" />
<img width="1512" height="861" alt="Screenshot 2026-03-31 at 1 23 07 PM" src="https://github.com/user-attachments/assets/87ef55e4-5314-4ea2-a8d1-aa40c3dfdd77" />


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
