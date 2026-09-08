-- Job Market Pulse mart: transparent rule-based job matching against user profile.
-- Formula: 0.35*skill + 0.25*role + 0.15*loc + 0.10*salary + 0.10*seniority + 0.05*recency
-- Scores live postings only; excludes hidden jobs.
-- Databricks SQL / Delta.

CREATE OR REPLACE VIEW mart_job_match AS
WITH profile AS (
  SELECT
    profile_id,
    COALESCE(target_roles, '["DE", "DA", "BI"]') AS target_roles,
    COALESCE(target_skills, '["SQL", "Python"]') AS target_skills,
    COALESCE(preferred_locations, '["Remote", "India"]') AS preferred_locations,
    COALESCE(remote_preference, 'ANY') AS remote_preference,
    COALESCE(min_salary, 0.0) AS min_salary,
    COALESCE(seniority_level, 'ENTRY') AS seniority_level
  FROM (
    SELECT * FROM user_profile LIMIT 1
  )
),
posting_skills AS (
  SELECT
    m.posting_id,
    COUNT(DISTINCT s.skill_name) AS skill_count,
    CONCAT_WS(', ', COLLECT_SET(s.skill_name)) AS matched_skills,
    SUM(CASE WHEN LOWER(s.skill_name) IN ('sql', 'python', 'spark', 'dbt', 'databricks') THEN 1.5 ELSE 1.0 END) AS weighted_skill_points
  FROM fact_posting_skill_mention m
  JOIN dim_skill s ON s.skill_id = m.skill_id
  GROUP BY m.posting_id
),
scored AS (
  SELECT
    f.posting_id,
    c.company_name,
    f.job_title,
    f.role_family,
    l.location_normalized AS location,
    f.date_posted,
    f.first_seen_at,
    f.last_seen_at,
    d.salary_min,
    d.salary_max,
    d.currency,
    d.employment_type,
    d.posting_url,
    d.apply_url,
    COALESCE(ps.matched_skills, '') AS matched_skills,
    COALESCE(ps.skill_count, 0) AS matched_skill_count,

    -- 1. Skill Match Score (0.0 to 1.0)
    LEAST(1.0, COALESCE(ps.weighted_skill_points, 0.0) / 6.0) AS skill_score,

    -- 2. Role Match Score (0.0 to 1.0)
    CASE
      WHEN p.target_roles LIKE CONCAT('%', f.role_family, '%') THEN 1.0
      WHEN f.role_family = 'OTHER' THEN 0.2
      ELSE 0.4
    END AS role_score,

    -- 3. Location Match Score (0.0 to 1.0)
    CASE
      WHEN p.remote_preference = 'ANY' THEN 1.0
      WHEN LOWER(l.location_normalized) LIKE '%remote%' THEN 1.0
      WHEN LOWER(l.location_normalized) LIKE '%india%' OR LOWER(l.location_normalized) LIKE '%bengaluru%' OR LOWER(l.location_normalized) LIKE '%bangalore%' THEN 1.0
      ELSE 0.4
    END AS location_score,

    -- 4. Salary Match Score (0.0 to 1.0)
    CASE
      WHEN d.salary_max IS NULL AND d.salary_min IS NULL THEN 0.7  -- Neutral when unknown
      WHEN d.salary_max IS NOT NULL AND d.salary_max >= p.min_salary THEN 1.0
      WHEN d.salary_min IS NOT NULL AND d.salary_min >= p.min_salary THEN 1.0
      ELSE 0.3
    END AS salary_score,

    -- 5. Seniority Match Score (0.0 to 1.0)
    CASE
      WHEN p.seniority_level = 'ENTRY' THEN
        CASE
          WHEN d.is_fresher OR d.experience_level = 'FRESHER' THEN 1.0
          WHEN d.experience_level = 'JUNIOR' THEN 0.95
          WHEN d.experience_level = 'MID' THEN 0.5
          WHEN d.experience_level IN ('SENIOR', 'LEAD') THEN 0.2
          WHEN LOWER(f.job_title) RLIKE '\\b(intern|junior|entry|associate|graduate|fresher)\\b' THEN 1.0
          WHEN LOWER(f.job_title) RLIKE '\\b(lead|principal|staff|director|head|vp|manager)\\b' THEN 0.2
          WHEN LOWER(f.job_title) RLIKE '\\b(senior|sr\\.?)\\b' THEN 0.3
          ELSE 0.85
        END
      WHEN p.seniority_level = 'SENIOR' THEN
        CASE
          WHEN d.experience_level IN ('SENIOR', 'LEAD') THEN 1.0
          WHEN d.experience_level = 'MID' THEN 0.8
          WHEN d.is_fresher OR d.experience_level = 'FRESHER' THEN 0.2
          WHEN LOWER(f.job_title) RLIKE '\\b(senior|sr\\.?|lead|staff|principal)\\b' THEN 1.0
          WHEN LOWER(f.job_title) RLIKE '\\b(intern|junior|entry|graduate)\\b' THEN 0.2
          ELSE 0.7
        END
      ELSE
        CASE
          WHEN d.experience_level = 'MID' THEN 1.0
          WHEN d.experience_level IN ('JUNIOR', 'SENIOR') THEN 0.85
          ELSE 0.8
        END
    END AS seniority_score,

    -- 6. Recency Score (0.0 to 1.0)
    CASE
      WHEN f.date_posted >= CURRENT_DATE() - INTERVAL 7 DAY THEN 1.0
      WHEN f.date_posted >= CURRENT_DATE() - INTERVAL 14 DAY THEN 0.8
      WHEN f.date_posted >= CURRENT_DATE() - INTERVAL 30 DAY THEN 0.6
      ELSE 0.4
    END AS recency_score,

    d.is_fresher,
    d.experience_level,
    d.min_years_exp,
    d.max_years_exp,
    ((f.closing_date IS NOT NULL AND f.closing_date < CURRENT_DATE()) OR f.last_seen_at < CURRENT_TIMESTAMP() - INTERVAL 7 DAY) AS is_likely_closed

  FROM fact_job_posting f
  CROSS JOIN profile p
  JOIN dim_company c
    ON c.company_id = f.company_id
    AND c.is_current = TRUE
  LEFT JOIN dim_location l
    ON l.location_id = f.location_id
  LEFT JOIN job_posting_detail d
    ON d.posting_id = f.posting_id
  LEFT JOIN posting_skills ps
    ON ps.posting_id = f.posting_id
  WHERE f.posting_id NOT IN (SELECT posting_id FROM hidden_jobs)
)
SELECT
  posting_id,
  company_name,
  job_title,
  role_family,
  location,
  date_posted,
  salary_min,
  salary_max,
  currency,
  employment_type,
  posting_url,
  apply_url,
  matched_skills,
  matched_skill_count,
  is_likely_closed,
  is_fresher,
  experience_level,
  min_years_exp,
  max_years_exp,
  ROUND((
    0.35 * skill_score +
    0.25 * role_score +
    0.15 * location_score +
    0.10 * salary_score +
    0.10 * seniority_score +
    0.05 * recency_score
  ) * 100, 1) AS match_score,
  ROUND(skill_score * 100, 1) AS skill_match_score,
  ROUND(role_score * 100, 1) AS role_match_score,
  ROUND(location_score * 100, 1) AS location_match_score,
  ROUND(salary_score * 100, 1) AS salary_match_score,
  ROUND(seniority_score * 100, 1) AS seniority_match_score,
  ROUND(recency_score * 100, 1) AS recency_score,
  first_seen_at,
  last_seen_at
FROM scored;
