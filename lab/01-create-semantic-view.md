# 01 - Create Semantic View

Build a semantic view over the aviation operations data. This gives Cortex Analyst (and your agent) a structured understanding of the flight data.

## What You Are Building

A semantic view named `FLIGHT_OPS_SV_<YOUR_ID>` that covers:
- **Flight schedules** - departures, arrivals, airlines, delays
- **Airline delay metrics** - daily aggregated delay statistics
- **Gate utilisation** - dwell times per gate per airline
- **Hourly traffic** - aircraft counts by hour and vehicle category

## Step 1: Create Your Schema

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE AVIA_LHR_WH;

-- Create a personal schema for your objects
CREATE SCHEMA IF NOT EXISTS AIRPORT_LHR.LAB_<YOUR_ID>;
USE SCHEMA AIRPORT_LHR.LAB_<YOUR_ID>;
```

## Step 2: Create the Semantic View

Copy and run the following SQL. Replace `<YOUR_ID>` with your participant identifier.

```sql
CREATE OR REPLACE SEMANTIC VIEW AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV

  TABLES (
    flight_schedule AS AIRPORT_LHR.PUBLIC.FLIGHT_SCHEDULE
      PRIMARY KEY (FLIGHT_KEY, FLIGHT_DATE)
      COMMENT = 'Flight schedule with departure/arrival times, delays, airlines, and gate assignments',

    airline_delay AS AIRPORT_LHR.PUBLIC.FLIGHT_TRAFFIC_FACT_AIRLINE_DELAY_DAILY
      UNIQUE ("DATE", AIRLINE)
      COMMENT = 'Daily aggregated delay and early-arrival metrics per airline',

    gate_dwell AS AIRPORT_LHR.PUBLIC.GATE_ANALYSIS_FLIGHT_DWELL_WITH_AIRLINE
      COMMENT = 'Per-flight gate dwell time with airline and gate assignment',

    hourly_traffic AS AIRPORT_LHR.PUBLIC.FLIGHT_TRAFFIC_FACT_ADSB_HOURLY
      UNIQUE (HOUR, VEHICLE_CATEGORY)
      COMMENT = 'Hourly aircraft counts by vehicle category from ADS-B data'
  )

  FACTS (
    flight_schedule.departure_delay AS DEPARTURE_DELAY
      COMMENT = 'Departure delay in minutes (negative = early)',
    flight_schedule.arrival_delay AS ARRIVAL_DELAY
      COMMENT = 'Arrival delay in minutes (negative = early)',
    airline_delay.total_delay_minutes AS TOTAL_DELAY_MINUTES
      COMMENT = 'Sum of delay minutes for the airline on this day',
    airline_delay.delayed_flights AS DELAYED_FLIGHTS
      COMMENT = 'Number of delayed flights for the airline on this day',
    airline_delay.total_early_minutes AS TOTAL_EARLY_MINUTES
      COMMENT = 'Sum of early-arrival minutes for the airline on this day',
    airline_delay.early_flights AS EARLY_FLIGHTS
      COMMENT = 'Number of early flights for the airline on this day',
    gate_dwell.dwell_minutes AS DWELL_MINUTES
      COMMENT = 'Minutes spent at the gate',
    hourly_traffic.aircraft_count AS AIRCRAFT_COUNT
      COMMENT = 'Number of distinct aircraft observed in the hour'
  )

  DIMENSIONS (
    -- Flight schedule dimensions
    flight_schedule.flight_date AS FLIGHT_DATE
      COMMENT = 'Date of the flight',
    flight_schedule.airline_name AS AIRLINE_NAME
      WITH SYNONYMS = ('carrier', 'airline')
      COMMENT = 'Full name of the operating airline',
    flight_schedule.airline_iata AS AIRLINE_IATA
      COMMENT = 'Two-letter IATA airline code',
    flight_schedule.departure_airport AS DEPARTURE_AIRPORT
      WITH SYNONYMS = ('origin', 'from airport')
      COMMENT = 'IATA code of departure airport',
    flight_schedule.arrival_airport AS ARRIVAL_AIRPORT
      WITH SYNONYMS = ('destination', 'to airport')
      COMMENT = 'IATA code of arrival airport',
    flight_schedule.flight_status AS FLIGHT_STATUS
      COMMENT = 'Status of the flight (scheduled, active, landed, cancelled)',
    flight_schedule.departure_terminal AS DEPARTURE_TERMINAL
      WITH SYNONYMS = ('terminal')
      COMMENT = 'Departure terminal identifier',
    flight_schedule.departure_gate AS DEPARTURE_GATE
      COMMENT = 'Departure gate identifier',
    flight_schedule.flight_number AS FLIGHT_NUMBER
      COMMENT = 'Airline flight number',

    -- Delay dimensions (NOTE: DATE is a reserved word, must be quoted)
    airline_delay.delay_date AS airline_delay."DATE"
      COMMENT = 'Date of the delay metric',
    airline_delay.delay_airline AS AIRLINE
      COMMENT = 'Airline name for delay metrics',

    -- Gate dwell dimensions
    gate_dwell.gate_name AS GATE_NAME
      WITH SYNONYMS = ('gate', 'stand')
      COMMENT = 'Gate or stand identifier',
    gate_dwell.gate_airline_name AS gate_dwell.AIRLINE_NAME
      COMMENT = 'Airline using the gate',
    gate_dwell.gate_service_date AS SERVICE_DATE
      COMMENT = 'Date of the gate service',
    gate_dwell.gate_vehicle_category AS gate_dwell.VEHICLE_CATEGORY
      COMMENT = 'Aircraft category at the gate',

    -- Traffic dimensions
    hourly_traffic.traffic_hour AS HOUR
      WITH SYNONYMS = ('time', 'hour of day')
      COMMENT = 'Hour timestamp for traffic measurement',
    hourly_traffic.traffic_vehicle_category AS hourly_traffic.VEHICLE_CATEGORY
      WITH SYNONYMS = ('aircraft type', 'category')
      COMMENT = 'Category of aircraft (e.g. large, medium, helicopter)'
  )

  METRICS (
    flight_schedule.total_flights AS COUNT(*)
      WITH SYNONYMS = ('flight count', 'number of flights')
      COMMENT = 'Total number of flights',
    flight_schedule.avg_departure_delay AS AVG(DEPARTURE_DELAY)
      WITH SYNONYMS = ('average delay')
      COMMENT = 'Average departure delay in minutes',
    flight_schedule.avg_arrival_delay AS AVG(ARRIVAL_DELAY)
      COMMENT = 'Average arrival delay in minutes',
    flight_schedule.delayed_flight_count AS COUNT_IF(DEPARTURE_DELAY > 0)
      COMMENT = 'Number of flights with a departure delay',
    gate_dwell.avg_dwell_minutes AS AVG(DWELL_MINUTES)
      WITH SYNONYMS = ('average gate time', 'turnaround time')
      COMMENT = 'Average gate dwell time in minutes',
    gate_dwell.max_dwell_minutes AS MAX(DWELL_MINUTES)
      COMMENT = 'Maximum gate dwell time in minutes',
    hourly_traffic.total_aircraft AS SUM(AIRCRAFT_COUNT)
      WITH SYNONYMS = ('total traffic', 'aircraft volume')
      COMMENT = 'Total aircraft observed',
    hourly_traffic.peak_aircraft AS MAX(AIRCRAFT_COUNT)
      COMMENT = 'Peak aircraft count in a single hour'
  )

  COMMENT = 'Aviation operations semantic view for LHR flight schedules, delays, gate utilisation, and traffic analysis'

  AI_SQL_GENERATION 'When no date filter is specified, use the most recent 7 days of data. Always round numeric results to 1 decimal place. For delay analysis, exclude flights with NULL departure_delay.'

  AI_VERIFIED_QUERIES (
    top_delayed_airlines AS (
      QUESTION 'Which airlines have the highest average departure delay?'
      SQL 'SELECT AIRLINE_NAME, AVG(DEPARTURE_DELAY) AS avg_delay_min
           FROM AIRPORT_LHR.PUBLIC.FLIGHT_SCHEDULE
           WHERE DEPARTURE_DELAY IS NOT NULL
           GROUP BY AIRLINE_NAME
           ORDER BY avg_delay_min DESC
           LIMIT 10'
      ONBOARDING_QUESTION TRUE
    ),
    busiest_hour AS (
      QUESTION 'What is the busiest hour at the airport?'
      SQL 'SELECT HOUR, SUM(AIRCRAFT_COUNT) AS total_aircraft
           FROM AIRPORT_LHR.PUBLIC.FLIGHT_TRAFFIC_FACT_ADSB_HOURLY
           GROUP BY HOUR
           ORDER BY total_aircraft DESC
           LIMIT 1'
      ONBOARDING_QUESTION TRUE
    ),
    longest_gate_dwell AS (
      QUESTION 'Which gates have the longest average dwell time?'
      SQL 'SELECT GATE_NAME, AVG(DWELL_MINUTES) AS avg_dwell, COUNT(*) AS flights
           FROM AIRPORT_LHR.PUBLIC.GATE_ANALYSIS_FLIGHT_DWELL_WITH_AIRLINE
           GROUP BY GATE_NAME
           HAVING COUNT(*) >= 5
           ORDER BY avg_dwell DESC
           LIMIT 10'
      ONBOARDING_QUESTION TRUE
    )
  );
```

## Step 3: Verify

```sql
-- Check it was created
SHOW SEMANTIC VIEWS IN SCHEMA AIRPORT_LHR.LAB_<YOUR_ID>;

-- Inspect dimensions and metrics
SHOW SEMANTIC DIMENSIONS IN AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV;
SHOW SEMANTIC METRICS IN AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV;

-- Quick test query via semantic view
SELECT * FROM SEMANTIC_VIEW(
  AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV
  METRICS flight_schedule.total_flights, flight_schedule.avg_departure_delay
  DIMENSIONS flight_schedule.airline_name
)
ORDER BY total_flights DESC
LIMIT 5;
```

## Step 4: Grant Permissions

Your agent and MCP server will need access:

```sql
GRANT REFERENCES, SELECT ON SEMANTIC VIEW AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV
  TO ROLE ACCOUNTADMIN;
```

---

**Next:** [02 - Create Cortex Agent](02-create-cortex-agent.md)
