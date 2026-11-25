"""Print the installed API and source used for the compatibility audit; no network."""
import inspect
import sys
from importlib.metadata import version

from pydexcom import Dexcom
from pydexcom.const import DEXCOM_TREND_DIRECTIONS, TREND_ARROWS
from pydexcom.glucose_reading import GlucoseReading

sys.stdout.reconfigure(encoding="utf-8")
print("pydexcom:", version("pydexcom"))
print("Dexcom:", inspect.signature(Dexcom))
print("Trend directions:", DEXCOM_TREND_DIRECTIONS)
print("Trend arrows:", TREND_ARROWS)
for item in (
    Dexcom.__init__, Dexcom._post, Dexcom._get_session,
    Dexcom.get_glucose_readings, Dexcom.get_current_glucose_reading,
    GlucoseReading.__init__, GlucoseReading.datetime.fget,
    GlucoseReading.mmol_l.fget, GlucoseReading.trend.fget,
    GlucoseReading.trend_arrow.fget, GlucoseReading.trend_direction.fget,
):
    print(inspect.getsource(item))
