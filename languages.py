"""English/Azerbaijani UI; prefer the desktop app's saved language."""
import json
import os
import re
import time
from pathlib import Path

WORDS={
 'Yeni status məlumatı gözlənilir':'Waiting for a new status update',
 'Mərhələ statusu yenilənməlidir':'Milestone status needs an update',
 'Mərhələlər tamamlandı':'Milestones complete',
 'Oxuma və axtarış':'Reading and searching','Fayl dəyişikliyi':'File change',
 'Test əməliyyatı':'Test action','Plan yenilənməsi':'Plan update',
 'Əmr əməliyyatı':'Command action','Alət əməliyyatı':'Tool action',
 'Növbəti əməliyyat hazırlanır':'Preparing the next action',
 'Claude açıldı':'Claude opened','söhbəti tətbiqdə seçin':'select the chat in the app',
 'Fayl oxuyur':'Reading a file','Faylları axtarır':'Finding files','Mətndə axtarır':'Searching text',
 'Planı yeniləyir':'Updating the plan','Planı oxuyur':'Reading the plan',
 'Claude alət xətası':'Claude tool error','Fon işi davam edir':'Background work continues',
 'Claude sessiyası bitdi':'Claude session ended','Claude status mənbəyi gözlənilir':'Waiting for Claude status events',
 'Claude status mənbəyi oxuna bilmir':'Claude status source cannot be read',
 'Claude tərəfindən bildirilib':'Reported by Claude','Claude hadisəsi qeydə alınıb':'Claude event observed',
 'Claude tərəfindən vəziyyət bildirilməsi gözlənilir':'Waiting for Claude to report status',
 'Colab canlı bağlantısı yoxdur':'No live Colab connection','Colab statusunu yenilə':'refresh Colab status',
 'uzaq hesabın son qeydi':'last remote calculation record','İterasiya məlum deyil':'Iteration unknown',
 'Məlumat oxunuşu gecikir':'Data reader is delayed','canlı əlaqə təsdiqlənmir':'live connection cannot be confirmed',
 'Ətraflı məlumat':'Details','Bildirişlər':'Notifications',
 'Məlumat mənbəyi oxuna bilmir':'Data source cannot be read',
 'Cari hesab tamamlandı':'Current calculation complete','nəticə auditi gözlənilir':'awaiting result audit',
 'Əvvəlki hesab tamamlandı':'Previous calculation complete','növbəti addıma keçildi':'advanced to the next step',
 'Gözləmə uzanır':'Waiting longer than expected','Diqqət tələb olunur':'Attention needed',
 'RAM gözləyir':'Waiting for RAM','RAM gözləyir · QE işləmir':'Waiting for RAM · QE is not running',
 'QE işləmir':'QE is not running','Proses yoxlanılır':'Checking process',
 'SCF başlanır':'Starting SCF','RAM məlumatı gözlənilir':'Waiting for RAM data',
 'yaddaş ayrıldıqda SCF başlayacaq':'SCF starts when RAM is available',
 'cari nəticənin auditi':'audit of the current result',
 'Əvvəlki hesabın bitməsini gözləyir':'Waiting for the upstream calculation',
 'Növbə gözləyir':'Queued','Proses işləyir':'Process is running',
 'Hesab bitdi':'Calculation finished','nəticə auditi gözlənilir':'awaiting result audit',
 'son jurnal göstərilir':'showing the last log','hesab dayandırılıb':'calculation stopped',
 'İstifadəçi dayandırıb':'Stopped by user','İdarəedici proses tapılmadı':'Controller process not found',
 'Validasiya zənciri tamamlandı':'Validation pipeline complete',
 'Cari hesabın faizi ölçülmür':'No percentage available for the current calculation',
 'CPU aktiv':'CPU active','CPU dəyişmir':'No CPU movement',
 'Söhbətə qayıt':'Return to chat','Bağla':'Quit','Dil':'Language',
 'Avtomatik (Codex)':'Automatic (Codex)','Mərkəzə gətir':'Center on screen',
 'Gözləyir':'Waiting','Codex sessiyası gözlənilir':'Waiting for a Codex session',
 'Tapşırığı araşdırır':'Reviewing the task','Cavab hazırdır':'Reply ready',
 'İşləyir':'Working','Dayandırıldı':'Stopped','İş dayandırılıb':'Work stopped',
 'Codex tapşırığı':'Codex task','Əmr icra edir':'Running a command',
 'Faylları dəyişir':'Editing files','Düşünür':'Thinking',
 'İstifadəçi cavabı gözlənilir':'Waiting for your reply',
 'Məlumat axtarır':'Searching','Alətlə işləyir':'Using a tool',
 'Açıq söhbət':'Open chat','Açıq söhbət gözlənilir':'Waiting for an open chat',
 'Bu söhbətin yerli vəziyyət qeydi yoxdur':'No local status for this chat',
 'Tətbiqdə bir söhbət açın':'Open a chat in the app',
 'Faiz ölçülmür':'Progress not measured','plan üzrə':'by plan steps',
 'iki kliklə söhbətə qayıt':'double-click to return',
 'SCF auditi':'SCF audit','Giriş-çıxış yoxlaması':'I/O validation',
 'Dalğa cutoff-u':'Wave cutoff','Sıxlıq cutoff-u':'Density cutoff',
 'Cüt cutoff yoxlaması':'Paired cutoff check','K-şəbəkə yoxlaması':'K-mesh check',
 'Yumşaq mod istiqaməti':'Soft-mode direction','Hesablama':'Calculation',
 'nəticə yoxlanır':'checking the result','yoxlama tələb olunur':'review required',
 'son qeydə alınan addım':'last recorded step','validasiya planı':'validation plan',
 'Hesablanır':'Computing','Yoxlama tələb olunur':'Review required',
 'Proses tapılmadı':'Process not found','Hesablama zənciri bitdi':'Calculation pipeline finished',
 'Nəticələr hazırdır':'Results ready','elmi şərh gözlənilir':'awaiting scientific interpretation',
 'Dayandırılıb':'Stopped','İşin canlı vəziyyəti oxuna bilmir':'Live job status unavailable',
 'Məlumat yoxdur':'No data','Son cavab işin tamamlanması deyil':'A reply does not mean the job is done',
 'Söhbət açıla bilmədi':'Could not open chat','yenidən yoxlayın':'try again',
}


def detect_language(home=None,appdata=None):
    home=Path(home or Path.home())
    appdata=Path(appdata or os.environ.get('APPDATA',home/'AppData/Roaming'))
    try:
        atoms=json.loads((home/'.codex/.codex-global-state.json').read_text(encoding='utf-8')).get('electron-persisted-atom-state',{})
        for key in ('locale','language','app-locale','app-language','ui-language','preferred-language'):
            value=atoms.get(key)
            if isinstance(value,str) and value.lower().startswith(('en','az')):
                return 'az' if value.lower().startswith('az') else 'en'
    except (OSError,ValueError,AttributeError):pass
    for profile in ('codex-browser-app','Default'):
        try:
            pref=json.loads((appdata/'Codex/web/Codex'/profile/'Preferences').read_text(encoding='utf-8'))
            intl=pref.get('intl',{})
            locale=intl.get('app_locale') or intl.get('selected_languages') or intl.get('accept_languages')
            if isinstance(locale,str) and locale:
                return 'az' if locale.lower().startswith('az') else 'en'
        except (OSError,ValueError,AttributeError):pass
    return 'en'


def translate(text,language):
    if language!='en':return text
    if text in WORDS:return WORDS[text]
    match=re.fullmatch(r'(\d+/\d+) addım',text)
    if match:return match[1]+' steps'
    match=re.fullmatch(r'Son müşahidə: (\d+) dəqiqə əvvəl',text)
    if match:return 'Last observed: '+match[1]+' min ago'
    match=re.fullmatch(r'(\d+/\d+) cutoff hesabı hazır',text)
    if match:return match[1]+' cutoff calculations complete'
    match=re.fullmatch(r'(\d+) Ry (keçdi|keçmədi)',text)
    if match:return match[1]+' Ry '+('passed' if match[2]=='keçdi' else 'failed')
    match=re.fullmatch(r'(jurnal|qeyd) (\d+) s əvvəl',text)
    if match:return ('log' if match[1]=='jurnal' else 'status')+' '+match[2]+' s ago'
    if ' · ' in text:return ' · '.join(translate(part,language) for part in text.split(' · '))
    if text.startswith('Sonra: '):
        return 'Next: '+translate(text[7:],language)
    suffix=' (yoxlama keçərsə)'
    if text.endswith(suffix):return translate(text[:-len(suffix)],language)+' (if validation passes)'
    if text=='nəticələrin qiymətləndirilməsi':return 'result assessment'
    match=re.fullmatch(r'(\d+/\d+) (mərhələ|addım)',text)
    if match:return match[1]+(' stages' if match[2]=='mərhələ' else ' steps')
    return text


class Language:
    def __init__(self):
        self.choice='auto'
        self.code='en'
        self.checked=-10

    def poll(self):
        if self.choice!='auto':self.code=self.choice
        elif time.monotonic()-self.checked>5:
            self.checked=time.monotonic()
            self.code=detect_language()
        return self.code

    def tr(self,text):return translate(text,self.code)


class DisplayState:
    def __init__(self,state,language):self.state,self.language=state,language
    def __getattr__(self,name):
        value=getattr(self.state,name)
        if name=='title' and value in ('Codex tapşırığı','Açıq söhbət','Açıq söhbət gözlənilir'):
            return translate(value,self.language)
        return translate(value,self.language) if name in ('current','next_step','progress_scope','live_metrics','live_health') else value
