from django.db import models
from django.db.models import Q
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext as _

class Party(models.Model):
    name = models.CharField(max_length = 10, primary_key=True)
    full_name = models.CharField(max_length = 50)
    logo = models.ImageField(upload_to = 'images/parties')
    info_link = models.URLField()

    def __unicode__(self):
        return self.full_name

class MemberManager(models.Manager):
    def active_in(self, date_begin, date_end):
        query = Q()
        if date_end:
            query &= Q(begin__lte=date_end)
        query &= Q(end__isnull=True) | Q(end__gte=date_begin)
        mem_list = PartyAssociation.objects.filter(query).distinct().values_list('member', flat=True)
        return self.filter(id__in=mem_list)
    def in_district(self, district, date_begin, date_end):
        query = Q(name = district)
        if date_end:
            query &= Q(begin__lte=date_end)
        query &= Q(end__isnull=True) | Q(end__gte=date_begin)
        mem_list = DistrictAssociation.objects.filter(query).distinct().values_list('member', flat=True)
        return self.filter(id__in=mem_list)

class Member(models.Model):
    name = models.CharField(max_length = 50, unique = True)
    url_name = models.SlugField(max_length = 50, unique = True)
    birth_date = models.DateField(blank = True, null = True)
    given_names = models.CharField(max_length = 50)
    surname = models.CharField(max_length = 50)

    email = models.EmailField()
    phone = models.CharField(max_length = 20)

    party = models.ForeignKey(Party, blank = True, null = True)
    photo = models.ImageField(upload_to = 'images/members')
    info_link = models.URLField()
    is_active = models.BooleanField()

    objects = MemberManager()

    def get_stats(self, begin, end):
        try:
            ms = MemberStats.objects.for_period(begin, end).get(member = self)
        except MemberStats.DoesNotExist:
            return None
        ms.calc()
        return ms

    def save(self, *args, **kwargs):
        if not self.url_name:
            # only do this with the first save
            self.url_name = slugify(self.name)
        super(Member, self).save(*args, **kwargs)

    def get_print_name(self):
        names = self.name.split()
        (last, first) = (names[0], names[1])
        return "%s %s" % (first, last)

    @models.permalink
    def get_absolute_url(self):
        return ('votes.views.show_member', (), {'member': self.url_name})

    def __unicode__(self):
        return self.name

class MemberStatsManager(models.Manager):
    def between(self, date_begin, date_end):
        query = Q()
        if date_end:
            query &= Q(begin__lte=date_end)
        if date_begin:
            query &= Q(end__isnull=True) | Q(end__gte=date_begin)
        return self.filter(query)
    def for_period(self, date_begin, date_end):
        return self.filter(begin=date_begin, end=date_end)

class MemberStats(models.Model):
    member = models.ForeignKey(Member)
    begin = models.DateField()
    end = models.DateField(blank = True, null = True)

    attendance = None
    party_agree = None
    session_agree = None

    # <agree>,<disagree>
    party_agreement = models.CommaSeparatedIntegerField(max_length = 20)
    session_agreement = models.CommaSeparatedIntegerField(max_length = 20)
    vote_counts = models.CommaSeparatedIntegerField(max_length = 30)
    statement_count = models.IntegerField()

    objects = MemberStatsManager()

    def __calc_attendance(self):
        vc = self.vote_counts.split(',')
        vcnt = {}
        # Clumsy... must be a better way
        for v in Vote.VOTE_CHOICES:
            vcnt[v[0]] = int(vc[Vote.VOTE_CHOICES.index(v)])
        return float(vcnt['Y'] + vcnt['N']) / (vcnt['Y'] + vcnt['N'] + vcnt['E'] + vcnt['A'])

    def __calc_agree(self, agr):
        n = agr.split(',')
        n = (int(n[0]), int(n[1]))
        if (n[0] + n[1] == 0):
            return float(0)     # FIXME
        return float(n[0]) / (n[0] + n[1])

    def calc(self):
        if not self.vote_counts:
            return
        self.attendance = self.__calc_attendance()
        self.party_agree = self.__calc_agree(self.party_agreement)
        self.session_agree = self.__calc_agree(self.session_agreement)


class DistrictAssociationManager(models.Manager):
    def between(self, date_begin, date_end):
        query = Q()
        if date_end:
            query &= Q(begin__lte=date_end)
        if date_begin:
            query &= Q(end__isnull=True) | Q(end__gte=date_begin)
        return self.filter(query)
    def list_between(self, date_begin, date_end):
        return self.between(date_begin, date_end).order_by('name').values_list('name', flat=True).distinct()

class DistrictAssociation(models.Model):
    member = models.ForeignKey(Member)
    name = models.CharField(max_length = 50)
    begin = models.DateField()
    end = models.DateField(blank = True, null = True)

    objects = DistrictAssociationManager()

class County(models.Model):
    name = models.CharField(max_length = 50)
    district = models.CharField(max_length = 50)
    class Meta:
        verbose_name_plural = "Counties"

    def __unicode__(self):
        return self.name

class PartyAssociation(models.Model):
    member = models.ForeignKey(Member)
    party = models.ForeignKey(Party)
    begin = models.DateField()
    end = models.DateField(blank = True, null = True)


class PlenarySessionManager(models.Manager):
    def between(self, begin = None, end = None):
        query = Q()
        if begin:
            query &= Q(date__gte=begin)
        if end:
            query &= Q(date__lte=end)
        return self.filter(query)

class PlenarySession(models.Model):
    name = models.CharField(max_length = 20, primary_key = True)
    date = models.DateField(db_index = True)
    info_link = models.URLField()
    url_name = models.SlugField(max_length = 20, unique = True, db_index = True)

    objects = PlenarySessionManager()

    def save(self, *args, **kwargs):
        if not self.url_name:
            self.url_name = self.name.replace('/', '-')
            # only do this with the first save
            self.url_name = slugify(self.url_name)
        super(PlenarySession, self).save(*args, **kwargs)
    def __unicode__(self):
        return self.name

class Minutes(models.Model):
    plenary_session = models.ForeignKey(PlenarySession)
    html = models.TextField()

    def __unicode__(self):
        return str(self.plenary_session) + " minutes"

class StatementManager(models.Manager):
    def between(self, begin = None, end = None):
        query = Q()
        if begin:
            query &= Q(plenary_session__date__gte=begin)
        if end:
            query &= Q(plenary_session__date__lte=end)
        return self.filter(query)

class Statement(models.Model):
    plenary_session = models.ForeignKey(PlenarySession)
    # Discussion number in plenary session minutes
    dsc_number = models.IntegerField()
    member = models.ForeignKey(Member, blank = True, null = True)
    # Index of statement in discussion
    index = models.IntegerField()
    text = models.TextField()
    html = models.TextField()

    objects = StatementManager()

    def __unicode__(self):
        if self.member:
            name = "%s %d / %d / %s - %s" % (_("Statement "), self.index+1,
                   self.dsc_number+1, self.plenary_session.name, self.member.name)
        else:
            name = "%s %d / %d / %s" % (_("Statement "), self.index+1,
                   self.dsc_number+1, self.plenary_session.name)
        return name


class SessionManager(models.Manager):
    def between(self, begin = None, end = None):
        query = Q()
        if begin:
            query &= Q(plenary_session__date__gte=begin)
        if end:
            query &= Q(plenary_session__date__lte=end)
        return self.filter(query)

class Session(models.Model):
    plenary_session = models.ForeignKey(PlenarySession)
    number = models.IntegerField()
    time = models.TimeField()
    info = models.TextField()
    subject = models.CharField(max_length = 100)
    info_link = models.URLField(blank = True, null = True)

    vote_counts = models.CommaSeparatedIntegerField(max_length = 20, blank = True, null = True)

    objects = SessionManager()

    def count_votes(self):
        if self.vote_counts:
            return
        vcnt = []
        for v in Vote.VOTE_CHOICES:
                c = Vote.objects.filter(session = self, vote = v[0]).count()
                vcnt.append(str(c))
        self.vote_counts = ','.join(vcnt)
        # Update db
        Session.objects.filter(pk = self.pk).update(vote_counts = self.vote_counts)

    def get_vote_counts(self):
        if not self.vote_counts:
            self.count_votes()
        vcnt = self.vote_counts.split(',')
        vdict = {}
        for i in range(len(Vote.VOTE_CHOICES)):
            v = Vote.VOTE_CHOICES[i]
            vdict[v[0]] = vcnt[i]
        return vdict

    def save(self, *args, **kwargs):
#        query = Q(begin__lte=self.plenary_session.date)
#        query &= Q(end__isnull=True) | Q(end__gte=self.plenary_session.date)
#        MemberStats.objects.filter(query).delete()
        super(Session, self).save(args, kwargs)

    def __unicode__(self):
        return str(self.number) + '/' + self.plenary_session.name

class SessionDocument(models.Model):
    sessions = models.ManyToManyField(Session)
    name = models.CharField(max_length = 20, db_index = True)
    url_name = models.SlugField(max_length = 20, unique = True)
    info_link = models.URLField()

    def save(self, *args, **kwargs):
        if not self.url_name:
            # only do this with the first save
            self.url_name = slugify(self.name)
        super(SessionDocument, self).save(*args, **kwargs)


class VoteManager(models.Manager):
    def get_count(self, vote = None, session = None, member = None):
        query = Q()
        if type(vote) is list:
            for v in vote:
                query |= Q(vote = v)
        elif vote is not None:
            query |= Q(vote = vote)
        if member is not None:
            query &= Q(member = member.name)
        if session is not None:
            query &= Q(session = session.name)

        return Vote.objects.filter(query).count()
    def in_district(self, district, date_begin, date_end):
        qs = Member.objects.in_district(district, date_begin, date_end)
        qs = qs.values_list('id', flat=True).distinct()
        return Vote.objects.filter(member__in=qs)

class Vote(models.Model):
    VOTE_CHOICES = [
        ('Y', u'Yes'),
        ('N', u'No'),
        ('A', u'Absent'),
        ('E', u'Empty'),
        ('S', u'Speaker')
    ]
    session = models.ForeignKey(Session)
    vote = models.CharField(max_length=1, choices=VOTE_CHOICES, db_index=True)
    member = models.ForeignKey(Member, db_index=True)
    party = models.CharField(max_length=10)

    objects = VoteManager()

    def __unicode__(self):
        return str(self.session) + ' / ' + self.member.name
