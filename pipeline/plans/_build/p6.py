from dsl import S, save
M = "Bright morning sun."
N = "Bright midday sun."
A = "Golden afternoon light."
E = "Golden evening light."
SING = "Close-up: {moss} sings to the camera, his mouth opening wide under his bushy mustache, "
SNAIL = "a small brown snail with a yellow racing stripe on its shell"
GRAN = "a grandma in a purple cardigan and pearl glasses"
DUCK = "a white duck with an orange beak"
save({
 "slug": "snail-race", "date": "2026-11-17", "product": "merch", "style": "claymation",
 "hook_text": "I lost a race to a snail",
 "song": {"title": "Slow Down",
  "style": "English, laid-back reggae with offbeat organ skank, deep round bass, rimshot drums and a melodica hook, warm friendly male lead vocal, slow and smiling, 110 BPM",
  "lyrics": "[Verse]\nAlways rushing, never slow\nFastest boots you'll ever know\nMet a snail beside the gate\nHe said race you, I can't wait\n\n[Chorus]\nSlow down, slow down, take your time\nSnail's ahead and I feel fine\nSlow down, slow down, smell the rose\nThat's the way the good stuff goes\n\n[Verse]\nI stopped to watch a bumblebee\nI stopped to climb the apple tree\nShared my lunch with a hungry duck\nSnail went past me, just my luck\n\n[Chorus]\nSlow down, slow down, take your time\nSnail has crossed the finish line\nSlow down, slow down, I came last\nWho knew losing was a blast"},
 "shots": [
  S(0, f"{{moss}} power-walks down a garden path at top speed, arms pumping, glancing at a pocket watch in his hand. The camera tracks backward fast in front of him. {M}"),
  S(None, f"Green rubber boots blur along a gravel path, kicking up little stones. Low angle close-up, the camera tracks with them. {M}"),
  S(1, f"{{moss}} zooms past {GRAN} who is watering her flowers, so fast that her watering can spins in her hand. The camera whip-pans as he passes. {M}", view="side"),
  S(None, f"Petals blow off a row of red tulips as something rushes past. Close-up, the camera whip-pans. {M}"),
  S(2, f"{{moss}} skids to a stop at a wooden garden gate and looks down at {SNAIL} sitting on the gatepost. The camera crash zooms from him to the snail. {M}", view="threeq",
    frame=f"He stands at a wooden garden gate bending forward to look closely at {SNAIL} on top of the gatepost. Medium shot. {M}"),
  S(None, f"{SNAIL[0].upper() + SNAIL[1:]} stretches up its eye stalks and stares, determined. Extreme close-up, the camera pushes in. {M}"),
  S(3, SING + f"amused, pointing down at {SNAIL} on a gatepost beside him. The camera pushes in. {M}", sing=True),
  S(None, f"A stick scratches a line across a dirt path, {SNAIL} waiting behind it beside two green rubber boots. Low angle, the camera pushes in. {M}"),
  S(4, f"{{moss}} crouches at a starting line on a dirt path in a sprinter's pose beside {SNAIL}. The camera orbits low around them. {M}"),
  S(None, f"{SNAIL[0].upper() + SNAIL[1:]} glides forward over a line scratched in the dirt, leaving a silver trail. Extreme close-up, the camera tracks with it. {M}"),
  S(5, f"{{moss}} strolls along a garden path with his hands in his raincoat pockets, smiling, far behind a tiny snail up ahead. The camera cranes up over him. {M}"),
  S(None, f"{SNAIL[0].upper() + SNAIL[1:]} looks back over its shell with one eye stalk. Close-up, the camera whip-pans to it. {M}"),
  S(6, f"{{moss}} buries his nose in a big pink rose on a rose bush and breathes in with his eyes closed. Close-up, the camera pushes in slowly. {N}", view="side",
    frame=f"He stands beside a rose bush leaning in with his nose touching a big pink rose, eyes closed, seen from the side. Medium shot. {N}"),
  S(None, f"A big pink rose opens its petals in the sun, a red ladybird on one petal. Extreme close-up, the camera orbits it. {N}"),
  S(7, SING + f"blissful, holding a big pink rose, a garden in bloom behind him. The camera orbits around him. {N}", sing=True),
  S(None, f"A silver snail trail winds along a garden path into the distance. Low angle, the camera tracks along it. {N}"),
  S(8, f"{{moss}} crouches by a patch of lavender, nose to nose with a fat fuzzy bumblebee on a flower. The camera pushes in. {N}", view="side"),
  S(None, f"A fat fuzzy bumblebee lifts off a lavender flower and bumbles around in a lazy loop. Close-up, the camera follows it. {N}"),
  S(9, f"{{moss}} sits on a branch of an apple tree swinging his boots and biting into a red apple. The camera cranes up to him. {N}"),
  S(None, f"A red apple with one bite taken out of it drops into the grass beside {SNAIL}, who glides on past it. Low angle, the camera tilts down. {N}"),
  S(10, f"{{moss}} sits on the bank of a pond sharing a sandwich with {DUCK}, who takes a big bite. The camera pushes in. {A}"),
  S(None, f"{DUCK[0].upper() + DUCK[1:]} gulps down a piece of bread and flaps happily. Close-up, the camera crash zooms in. {A}"),
  S(11, f"{SNAIL[0].upper() + SNAIL[1:]} glides past two green rubber boots dangling over the edge of a pond. Low angle close-up, the camera tracks with the snail. {A}"),
  S(None, f"{{moss}} looks down, spots a snail overtaking him, and slaps his forehead with a laugh. The camera crash zooms in. {A}",
    frame=f"He sits on the grassy bank of a pond looking down beside him in surprise at {SNAIL} gliding past. Medium shot. {A}"),
  S(12, SING + f"relaxed and happy, strolling along a garden path with his hands in his raincoat pockets. The camera tracks backward in front of him. {A}", sing=True),
  S(None, f"{GRAN[0].upper() + GRAN[1:]} holds one end of a red ribbon stretched across a garden path as a finish line and waves a little green flag. The camera pushes in. {A}"),
  S(13, f"A cream t-shirt with a hills-and-infinity-path illustration and the words Infinite Stroll hangs on a wooden fence beside a garden path, fluttering gently in the breeze, a red ribbon finish line stretched across the path below it. The camera drifts slowly toward it. {A}", product=True),
  S(None, f"{SNAIL[0].upper() + SNAIL[1:]} glides through a red ribbon finish line in slow motion. Extreme close-up, the camera tracks with it. {A}"),
  S(14, f"{{moss}} strolls up to a red ribbon finish line long afterwards and bows to {GRAN}, who claps. The camera orbits around them. {E}"),
  S(None, f"{SNAIL[0].upper() + SNAIL[1:]} sits on a tiny upturned flowerpot like a winner's podium, a daisy chain around its shell. Close-up, the camera pushes in. {E}"),
  S(15, f"{{moss}} lifts {SNAIL} up on his open palm like a champion and laughs. The camera crash zooms in. {E}"),
  S(None, f"{{moss}} lies in the grass at sunset with a small snail resting on the toe of his green boot, watching the sky turn pink and breathing out slowly. The camera cranes slowly up. {E}"),
 ],
 "endcard": {"line1": "Take the slow way.", "line2": "link in bio"},
 "caption": "moss raced a snail and lost by hours. he stopped for a bee, an apple and a duck. the Infinite Stroll tee marked the finish",
 "hashtags": ["#slowliving", "#snail", "#claymation", "#solarpunk", "#touchgrass"],
})
