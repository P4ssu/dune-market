DUNE MARKET - hinnapopup Dune: Awakeningu jaoks
================================================

Mida see teeb
- Kui hoiad hiirt inventory itemil, ilmub tooltipi kohale popup: keskmine hind, odavaim pakkumine,
  trend, pakkumiste arv ja kui vana info on.
- Kui avad Exchange'i (Buy / Sell tab), loeb programm ekraanilt hinnad ja salvestab need.
  Hinnad jagatakse sõpradega ühte andmebaasi, nii et iga sõbra skannitud hinnad on kõigile nähtavad.

Paigaldus (ainult esimene kord)
1. Paki see kaust lahti kuhu tahad (nt Töölaud). Ära jooksuta .zip seest.
2. Ava fail  config.toml  Notepadiga ja kirjuta rida  contributor = "..."  sisse oma nimi. Salvesta.
3. Mängus: Settings -> Graphics -> Display mode = "Windowed Fullscreen" (borderless).
   Täisekraanis popup ei ilmu.
4. Topeltklõpsa  DuneMarket.exe.
   Windows võib kirjutada "Windows protected your PC". Vali "More info" ja "Run anyway"
   (programm pole allkirjastatud).
5. Must aken (konsool) jääb avatuks, ära sulge seda. Mängu peal ilmub mõne sekundi pärast teade
   "Dune Market - Running".

Kasutamine
- Hindade kogumine: ava mängus Exchange ja vaata Sell-tabi (näitab sinu seljakoti hindu) või
  Buy-tabi (scrolli kategooriaid). Ekraani ülaossa ilmub teade, mitu rida loeti ja kui palju oli uusi.
  Mida rohkem sõpru itemeid skannib, seda täpsemad hinnad.
- Hinna vaatamine: hoia hiirt inventory itemil või blueprintil.
- Hinnaotsing: vajuta Ctrl+Shift+F, kirjuta itemi nimi (nt "cobalt paste") ja näed kõiki hindu
  koos gradeiga. Esc või sama klahv uuesti sulgeb. Klahvi saab muuta failis config.toml
  (rida search_hotkey, nt "F8").
- Peatamine: sulge must konsooliaken.

Kui popup ei ilmu mängu peale
- Kasuta  start-solid.bat  (topeltklõps) DuneMarket.exe asemel.

Privaatsus ja märkused
- Programm vaatab ekraani ainult siis, kui Dune: Awakening on aktiivne aken. See ei puutu mängu
  faile, mälu ega võrguliiklust ega saada mängule midagi.
- Andmebaasi lähevad ainult hinnad, itemite nimed ja sinu config.toml'is olev nimi. Ekraanipilte
  ei salvestata ega saadeta.
- See on mitteametlik tööriist. Funcom ei ole seda kinnitanud. Kasuta omal vastutusel.
- Hinnad on World'i põhised. Praegu jagatakse ainult World'i Andromeda hindu.
