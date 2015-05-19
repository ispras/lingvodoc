'use strict';

define([], function() {
    var elan = {};

    var _forEach = Array.prototype.forEach;
    var _map = Array.prototype.map;

    elan.TimeSlot = function(id, value) {
        this.id = id;
        this.value = value;
    };

    elan.Annotation = function(id, value, timeslotRef1, timeslotRef2) {
        this.id = id;
        this.value = value;
        this.timeslotRef1 = timeslotRef1;
        this.timeslotRef2 = timeslotRef2;
    };

    elan.Tier = function(id, linguisticTypeRef, defaultLocale, annotations) {
        this.id = id;
        this.defaultLocale = defaultLocale;
        this.linguisticTypeRef = linguisticTypeRef;
        this.annotations = annotations;
    };

    elan.Document = function() {
        this.mediaFile = '';
        this.mediaUrl = '';
        this.mediaType = '';
        this.timeslots = [];
        this.tiers = [];

        this.lastUsedTierId = 0;
        this.lastUsedAnnoationId = 0;
        this.lastUsedTimeSlotId = 0;

        var timeslotExists = function(ts, list) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].id == ts.id) {
                    return true;
                }
            }
            return false;
        };


        this.getTimeSlot = function(slotId) {
            for (var i = 0; i < this.timeslots.length; i++) {
                var timeslot = this.timeslots[i];
                if (timeslot.id == slotId) {
                    return timeslot;
                }
            }
        }.bind(this);


        this.getTimeSlotByValue = function(value) {
            for (var i = 0; i < this.timeslots.length; i++) {
                var timeslot = this.timeslots[i];
                if (timeslot.value === value) {
                    return timeslot;
                }
            }
        }.bind(this);


        this.getValidTimeslots = function() {
            var validTimeslots = [];
            for (var i = 0; i < this.tiers.length; i++) {
                var tier = this.tiers[i];
                for (var j = 0; j < tier.annotations.length; j++) {
                    var annotation = tier.annotations[j];
                    if (annotation instanceof elan.Annotation) {
                        var timeslot1 = this.getTimeSlot(annotation.timeslotRef1);
                        var timeslot2 = this.getTimeSlot(annotation.timeslotRef2);
                        if (typeof timeslot1 != 'undefined' && typeof timeslot2 != 'undefined') {

                            if (!timeslotExists(timeslot1, validTimeslots)) {
                                validTimeslots.push(timeslot1);
                            }

                            if (!timeslotExists(timeslot2, validTimeslots)) {
                                validTimeslots.push(timeslot2);
                            }
                        }
                    }
                }
            }

            // sort timeslots by value
            validTimeslots.sort(function(a, b) {
                if (a.value > b.value)
                    return 1;
                if (a.value < b.value)
                    return -1;
                return 0;
            });

            return validTimeslots;
        }.bind(this);

        this.getTier = function(id) {
            var tier = null;
            for (var i = 0; i < this.tiers.length; i++) {
                if (this.tiers[i].id === id) {
                    tier = this.tiers[i];
                    break;
                }
            }
            return tier;
        }.bind(this);


        this.importXML = function(xml) {

            var header = xml.querySelector('HEADER');
            var inMilliseconds = header.getAttribute('TIME_UNITS') == 'milliseconds';
            var media = header.querySelector('MEDIA_DESCRIPTOR');
            this.mediaUrl = media.getAttribute('MEDIA_URL');
            this.mediaType = media.getAttribute('MIME_TYPE');

            var timeSlots = xml.querySelectorAll('TIME_ORDER TIME_SLOT');
            _forEach.call(timeSlots, function (slot) {
                var slotId = slot.getAttribute('TIME_SLOT_ID');
                var value = parseFloat(slot.getAttribute('TIME_VALUE'));
                // If in milliseconds, convert to seconds with rounding
                if (!inMilliseconds) {
                    value = Math.floor(value * 1000);
                }

                var s = this.getTimeSlot(slotId);
                if (typeof s == 'undefined') {
                    this.timeslots.push(new elan.TimeSlot(slotId, value));
                }
            }.bind(this));

            this.tiers = _map.call(xml.querySelectorAll('TIER'), function (tier) {
                var tierId = tier.getAttribute('TIER_ID');
                var linguisticTypeRef = tier.getAttribute('LINGUISTIC_TYPE_REF');
                var defaultLocale = tier.getAttribute('DEFAULT_LOCALE');
                var annotations = _map.call(
                    tier.querySelectorAll('ALIGNABLE_ANNOTATION'),
                    function (node) {
                        var annotationId = node.getAttribute('ANNOTATION_ID');
                        var value = node.querySelector('ANNOTATION_VALUE').textContent.trim();
                        var start = node.getAttribute('TIME_SLOT_REF1');
                        var end = node.getAttribute('TIME_SLOT_REF2');
                        return new elan.Annotation(annotationId, value, start, end);
                    }, this
                );

                return new elan.Tier(tierId, linguisticTypeRef, defaultLocale, annotations);
            }, this);

        }.bind(this);


        this.exportXML = function() {

            var doc = document.implementation.createDocument(null, 'ANNOTATION_DOCUMENT', null);

            // create document header
            var headerElement = doc.createElement('HEADER');
            headerElement.setAttribute('MEDIA_FILE', this.mediaFile);
            headerElement.setAttribute('TIME_UNITS', 'milliseconds');

            var mediaDescriptorElement = doc.createElement('MEDIA_DESCRIPTOR');
            mediaDescriptorElement.setAttribute('MEDIA_URL', this.mediaUrl);
            headerElement.appendChild(mediaDescriptorElement);

            var prop1Element = doc.createElement('PROPERTY');
            prop1Element.setAttribute('NAME', 'URN');
            prop1Element.textContent = 'urn:nl-mpi-tools-elan-eaf:dd04600d-3cc3-41a3-a102-548c7b8c0e45';
            headerElement.appendChild(prop1Element);

            var prop2Element = doc.createElement('PROPERTY');
            prop2Element.setAttribute('NAME', 'lastUsedAnnotationId');
            prop2Element.textContent = this.lastUsedAnnoationId;
            headerElement.appendChild(prop2Element);

            doc.documentElement.appendChild(headerElement);

            var validTimeslots = this.getValidTimeslots();

            var timeOrderElement = doc.createElement('TIME_ORDER');
            validTimeslots.forEach(function(slot) {
                var slotElement = doc.createElement('TIME_SLOT');
                slotElement.setAttribute('TIME_SLOT_ID', slot.id);
                slotElement.setAttribute('TIME_VALUE', slot.value);
                timeOrderElement.appendChild(slotElement);
            });

            doc.documentElement.appendChild(timeOrderElement);

            for (var i = 0; i < this.tiers.length; i++) {

                var tier = this.tiers[i];
                var tierElement = doc.createElement('TIER');
                tierElement.setAttribute('TIER_ID', tier.id);
                tierElement.setAttribute('LINGUISTIC_TYPE_REF', tier.linguisticTypeRef);

                for (var j = 0; j < tier.annotations.length; j++) {
                    var an = tier.annotations[j];

                    var annotationElement = doc.createElement('ANNOTATION');
                    var allignableAnnotationElement = doc.createElement('ALIGNABLE_ANNOTATION');

                    allignableAnnotationElement.setAttribute('ANNOTATION_ID', an.id);
                    allignableAnnotationElement.setAttribute('TIME_SLOT_REF1', an.timeslotRef1);
                    allignableAnnotationElement.setAttribute('TIME_SLOT_REF2', an.timeslotRef2);

                    var annotationValueElement = doc.createElement('ANNOTATION_VALUE');
                    annotationValueElement.textContent = an.value;

                    allignableAnnotationElement.appendChild(annotationValueElement);
                    annotationElement.appendChild(allignableAnnotationElement);
                    tierElement.appendChild(annotationElement);
                }
                doc.documentElement.appendChild(tierElement);
            }

            var serializer = new XMLSerializer();
            return serializer.serializeToString(doc);
        }.bind(this);


        this.createTier = function(linguisticTypeRef, defaultLocale) {
            var tierId = 'tier' + this.lastUsedTierId;
            this.lastUsedTierId++;
            this.tiers.push(new elan.Tier(tierId, linguisticTypeRef, 'default-locale', []));
            return tierId;
        }.bind(this);


        this.createAnnotation = function(tierId, value, from, to) {
            var tier = this.getTier(tierId);
            if (tier != null) {
                var ts1 = this.getTimeSlotByValue(from);
                if (typeof ts1 == 'undefined') {
                    ts1 = new elan.TimeSlot('ts' + this.lastUsedTimeSlotId, from);
                    this.lastUsedTimeSlotId++;
                    this.timeslots.push(ts1);
                }

                var ts2 = this.getTimeSlotByValue(to);
                if (typeof ts2 == 'undefined') {
                    ts2 = new elan.TimeSlot('ts' + this.lastUsedTimeSlotId, to);
                    this.lastUsedTimeSlotId++;
                    this.timeslots.push(ts2);
                }
                var annotationId = 'an' + this.lastUsedAnnoationId;
                this.lastUsedAnnoationId++;
                var annotation = new elan.Annotation(annotationId, value, ts1.id, ts2.id);
                tier.annotations.push(annotation);
                return annotationId;
            }
            return null;
        }.bind(this);
    };

    return elan;
});
