export interface GlossaryEntry {
  definition: string;
  noviceExplanation: string;
  example: string;
}

export const glossary: Record<string, GlossaryEntry> = {
  'Trail Braking': {
    definition:
      'Gradually releasing brake pressure while turning in, transferring weight to the front tires for better grip through the corner entry.',
    noviceExplanation:
      'Instead of fully releasing the brake before you turn, keep some brake pressure as you start turning. This pushes the front of the car down, giving the front tires more grip.',
    example:
      'Approaching Turn 5: Brake at the 3-board, then slowly ease off the brake as you turn in toward the apex.',
  },
  Apex: {
    definition:
      'The innermost point of your line through a corner. Early apex = before geometric center, late apex = after.',
    noviceExplanation:
      'The closest point to the inside of a turn. Think of it as the "tip" of your path through a curve.',
    example:
      'In a 90-degree right turn, the apex is where your car is closest to the right-side curbing.',
  },
  'Min Speed': {
    definition:
      'Your lowest speed through the corner. Higher min speed = better momentum and faster exit.',
    noviceExplanation:
      'The slowest you go in a corner. Going faster through the corner (safely) means a faster lap time.',
    example:
      'If your min speed in Turn 3 is 55mph but the fast guys do 60mph, you are overslowing the car.',
  },
  'Throttle Commit': {
    definition:
      'The point where you go to full throttle on corner exit. Earlier commit (with good technique) = faster lap.',
    noviceExplanation:
      'Where you step on the gas fully after a turn. Getting on the gas earlier (when it is safe) means more speed down the next straight.',
    example:
      'After the apex of Turn 1, getting to full throttle 10 meters earlier gains 0.2s by the end of the straight.',
  },
  'Brake Point': {
    definition:
      'Where you first apply the brakes before a corner. Consistency here is more important than late braking.',
    noviceExplanation:
      'The spot where you start pressing the brake pedal. Braking at the same spot every lap is more important than braking super late.',
    example: 'Use the 3-board (150m marker) as your consistent brake point for Turn 5.',
  },
  'Peak Brake G': {
    definition:
      'Maximum deceleration force during braking, measured in G-forces. Higher = harder braking.',
    noviceExplanation:
      'How hard you hit the brakes. 1G means you are decelerating at the same rate as gravity.',
    example: 'A typical track day car can achieve 0.8-1.2G of braking force.',
  },
  'Consistency Score': {
    definition:
      'How similar your lap times are to each other. Lower variance = higher consistency = faster overall pace.',
    noviceExplanation:
      'A number showing how repeatable your driving is. If your laps are all similar times, your consistency is high.',
    example:
      'Lap times of 1:25.1, 1:25.3, 1:25.0 = high consistency. 1:25.1, 1:28.4, 1:23.9 = low consistency.',
  },
  'Ideal Lap': {
    definition:
      'A theoretical lap combining your best sector times from different laps — the fastest possible if you drove every section perfectly.',
    noviceExplanation:
      'An imaginary "perfect" lap made by stitching together your best parts from different laps.',
    example:
      'If your best sector 1 was on lap 3 and best sector 2 was on lap 7, the ideal lap combines both.',
  },
  'Delta-T': {
    definition:
      'Time difference between two laps at each point on track. Negative = faster than reference.',
    noviceExplanation:
      'Shows whether you are ahead or behind compared to another lap. Red means slower, green means faster.',
    example:
      'A delta of -0.3s at the braking zone means you arrived 0.3 seconds earlier than the reference lap.',
  },
  'Traction Circle': {
    definition:
      "Visualization of combined lateral and longitudinal G-forces. A fuller circle means you're using more of the tire's grip potential.",
    noviceExplanation:
      'A chart showing how much grip you are using. A bigger, more filled-in circle means you are driving closer to the limit.',
    example:
      'Pros have a nearly full traction circle; beginners often only use 50-60% of available grip.',
  },
};
